"""
智能门锁快递看护模式管理器

管理快递看护模式的生命周期，包括：
- 看护模式启用/关闭
- 基准图片管理
- 监控循环（每5秒拍照）
- VLLM威胁分析
- 威胁等级响应
"""
import os
import asyncio
import base64
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path
from loguru import logger

from .models import PackageAlert
from .doorlock_database import DoorlockDatabase

TAG = "PackageGuardManager"


class PackageGuardManager:
    """快递看护模式管理器"""
    
    def __init__(
        self,
        db: DoorlockDatabase,
        vllm_provider,
        tts_provider,
        notification_service,
        config: dict
    ):
        """初始化看护模式管理器
        
        Args:
            db: 数据库服务
            vllm_provider: VLLM服务提供者
            tts_provider: TTS服务提供者
            notification_service: 通知服务
            config: 配置字典
        """
        self.db = db
        self.vllm_provider = vllm_provider
        self.tts_provider = tts_provider
        self.notification_service = notification_service
        self.config = config  # 保存完整配置
        
        # 配置参数
        self.photo_interval = config.get('photo_interval', 5)  # 拍照间隔（秒）
        self.baseline_dir = config.get('baseline_dir', 'data/face_recognition/package_baseline/')
        
        # 确保基准图片目录存在
        Path(self.baseline_dir).mkdir(parents=True, exist_ok=True)
        
        # 监控任务管理
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        
        # 基准图片缓存
        self._baseline_cache: Dict[str, bytes] = {}
        
        logger.bind(tag=TAG).info(
            f"看护模式管理器初始化完成: photo_interval={self.photo_interval}s, "
            f"baseline_dir={self.baseline_dir}"
        )
    
    async def enable_guard(self, device_id: str, reason: str) -> bool:
        """启用看护模式
        
        Args:
            device_id: 设备ID
            reason: 启用原因
            
        Returns:
            是否启用成功
        """
        try:
            # 获取设备配置
            config = await self.db.get_config(device_id)
            
            # 检查 package_guard_available
            if not config.package_guard_available:
                logger.bind(tag=TAG).warning(
                    f"看护模式不可用: device_id={device_id}, "
                    f"package_guard_available=False"
                )
                return False
            
            # 更新配置
            config.package_guard_active = True
            config.package_guard_start_time = datetime.now()
            
            success = await self.db.update_config(config)
            
            if success:
                logger.bind(tag=TAG).info(
                    f"启用看护模式成功: device_id={device_id}, reason={reason}"
                )
                
                # 发送状态变化通知
                await self.notification_service.notify_guard_status_change(
                    device_id=device_id,
                    active=True,
                    reason=reason,
                    baseline_image=config.package_baseline_image,
                    start_time=config.package_guard_start_time
                )
            else:
                logger.bind(tag=TAG).error(
                    f"启用看护模式失败: device_id={device_id}"
                )
            
            return success
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"启用看护模式异常: device_id={device_id}, error={e}"
            )
            return False
    
    async def disable_guard(self, device_id: str, reason: str) -> bool:
        """关闭看护模式
        
        Args:
            device_id: 设备ID
            reason: 关闭原因
            
        Returns:
            是否关闭成功
        """
        try:
            # 停止监控循环
            await self.stop_monitoring(device_id)
            
            # 获取设备配置
            config = await self.db.get_config(device_id)
            
            # 更新配置
            config.package_guard_active = False
            
            success = await self.db.update_config(config)
            
            if success:
                logger.bind(tag=TAG).info(
                    f"关闭看护模式成功: device_id={device_id}, reason={reason}"
                )
                
                # 发送状态变化通知
                await self.notification_service.notify_guard_status_change(
                    device_id=device_id,
                    active=False,
                    reason=reason,
                    baseline_image=None,
                    start_time=None
                )
            else:
                logger.bind(tag=TAG).error(
                    f"关闭看护模式失败: device_id={device_id}"
                )
            
            return success
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"关闭看护模式异常: device_id={device_id}, error={e}"
            )
            return False
    
    async def update_baseline(self, device_id: str, image_data: bytes = None) -> str:
        """更新基准图片
        
        Args:
            device_id: 设备ID
            image_data: 图片数据（可选，如果不提供则需要拍照）
            
        Returns:
            基准图片路径，失败返回空字符串
        """
        try:
            # 生成基准图片路径
            timestamp = int(datetime.now().timestamp())
            filename = f"device_{device_id}_baseline_{timestamp}.jpg"
            baseline_path = os.path.join(self.baseline_dir, filename)
            
            # 如果没有提供图片数据，需要拍照
            if image_data is None:
                logger.bind(tag=TAG).warning(
                    f"更新基准图片需要图片数据: device_id={device_id}"
                )
                return ""
            
            # 保存基准图片
            with open(baseline_path, 'wb') as f:
                f.write(image_data)
            
            # 更新缓存
            self._baseline_cache[device_id] = image_data
            
            # 更新数据库配置
            config = await self.db.get_config(device_id)
            config.package_baseline_image = baseline_path
            await self.db.update_config(config)
            
            logger.bind(tag=TAG).info(
                f"更新基准图片成功: device_id={device_id}, path={baseline_path}"
            )
            
            return baseline_path
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"更新基准图片异常: device_id={device_id}, error={e}"
            )
            return ""
    
    async def start_monitoring(self, device_id: str, session_id: str, conn):
        """启动监控循环（事件驱动模式）
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            conn: 连接对象（用于检查PIR状态）
            
        说明:
            优化后的监控模式：
            1. 等待PIR检测到人体（低功耗等待）
            2. PIR触发后进入高频监控（每3秒拍照）
            3. PIR超时（2秒无上报）后退出高频监控
            4. 返回步骤1，继续等待
        """
        # 如果已经有监控任务在运行，先停止
        if device_id in self._monitoring_tasks:
            await self.stop_monitoring(device_id)
        
        # 创建监控任务
        task = asyncio.create_task(
            self._monitoring_loop(device_id, session_id, conn)
        )
        self._monitoring_tasks[device_id] = task
        
        logger.bind(tag=TAG).info(
            f"启动事件驱动监控循环: device_id={device_id}, session_id={session_id}"
        )
    
    async def stop_monitoring(self, device_id: str):
        """停止监控循环
        
        Args:
            device_id: 设备ID
        """
        if device_id in self._monitoring_tasks:
            task = self._monitoring_tasks[device_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._monitoring_tasks[device_id]
            
            logger.bind(tag=TAG).info(f"停止监控循环: device_id={device_id}")
    
    async def is_active(self, device_id: str) -> bool:
        """检查看护模式是否激活
        
        Args:
            device_id: 设备ID
            
        Returns:
            是否激活
        """
        try:
            config = await self.db.get_config(device_id)
            return config.package_guard_active
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"检查看护模式状态异常: device_id={device_id}, error={e}"
            )
            return False
    
    async def _monitoring_loop(self, device_id: str, session_id: str, conn):
        """监控循环（事件驱动模式）
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            conn: 连接对象
            
        说明:
            事件驱动监控流程：
            1. 等待PIR检测到人体（协程挂起，不消耗资源）
            2. PIR触发 → 进入高频监控模式（每3秒拍照）
            3. PIR超时（2秒无上报）→ 退出高频监控
            4. 返回步骤1
        """
        logger.bind(tag=TAG).info(
            f"事件驱动监控循环开始: device_id={device_id}, session_id={session_id}"
        )
        
        try:
            while True:
                # 检查看护模式是否仍然激活
                if not await self.is_active(device_id):
                    logger.bind(tag=TAG).info(
                        f"看护模式已关闭，停止监控: device_id={device_id}"
                    )
                    break
                
                # 步骤1: 等待PIR检测到人体（低功耗等待）
                logger.bind(tag=TAG).debug(
                    f"等待PIR检测人体 - 设备: {device_id}"
                )
                await self._wait_for_pir_detection(conn)
                
                # 检查看护模式是否仍然激活
                if not await self.is_active(device_id):
                    break
                
                # 步骤2: PIR触发，进入高频监控模式
                logger.bind(tag=TAG).info(
                    f"PIR检测到人体，进入高频监控模式 - 设备: {device_id}"
                )
                await self._high_frequency_monitoring(device_id, session_id, conn)
                
                # 步骤3: 高频监控结束（PIR超时），返回等待状态
                logger.bind(tag=TAG).info(
                    f"PIR超时，人体已离开，返回等待状态 - 设备: {device_id}"
                )
                
        except asyncio.CancelledError:
            logger.bind(tag=TAG).info(
                f"监控循环被取消: device_id={device_id}, session_id={session_id}"
            )
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"监控循环异常: device_id={device_id}, session_id={session_id}, error={e}"
            )
    
    async def _wait_for_pir_detection(self, conn):
        """等待PIR检测到人体（协程挂起，不消耗CPU资源）
        
        Args:
            conn: 连接对象
            
        说明:
            此方法会阻塞直到PIR检测到人体。
            通过检查 conn.pir_detected 和 PIR超时状态来判断。
        """
        from core.utils.pir_utils import check_pir_status
        
        while True:
            # 检查PIR是否检测到人体且未超时
            if hasattr(conn, 'pir_detected') and conn.pir_detected:
                if check_pir_status(conn, timeout=2.0):
                    # PIR正常，人体仍在
                    logger.bind(tag=TAG).debug(
                        f"PIR检测到人体 - 设备: {conn.device_id}"
                    )
                    return
            
            # 等待0.5秒后再次检查（避免过于频繁的检查）
            await asyncio.sleep(0.5)
    
    async def _high_frequency_monitoring(self, device_id: str, session_id: str, conn):
        """高频监控模式（有人时每3秒拍照分析）
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            conn: 连接对象
            
        说明:
            在PIR检测到人体后进入此模式，每3秒拍照并分析威胁等级。
            当PIR超时（2秒无上报）时自动退出。
        """
        # 从配置读取监控间隔（默认3秒）
        monitoring_interval = self.config.get('doorlock', {}).get(
            'package_guard', {}
        ).get('monitoring_interval', 3)
        
        logger.bind(tag=TAG).info(
            f"开始高频监控 - 设备: {device_id}, 间隔: {monitoring_interval}秒"
        )
        
        while True:
            # 检查看护模式是否仍然激活
            if not await self.is_active(device_id):
                logger.bind(tag=TAG).info(
                    f"看护模式已关闭，退出高频监控 - 设备: {device_id}"
                )
                return
            
            # 检查PIR状态（人是否已离开）
            if not self._check_pir_status(conn):
                logger.bind(tag=TAG).info(
                    f"PIR超时，人体已离开，退出高频监控 - 设备: {device_id}"
                )
                return
            
            # 执行拍照和分析
            await self._capture_and_analyze(device_id, session_id)
            
            # 等待指定间隔
            await asyncio.sleep(monitoring_interval)
    
    def _check_pir_status(self, conn) -> bool:
        """检查PIR状态（人体是否仍在）
        
        Args:
            conn: 连接对象
            
        Returns:
            True: PIR正常，人体仍在
            False: PIR超时，人体已离开
        """
        from core.utils.pir_utils import check_pir_status
        
        # 从配置读取PIR超时阈值（默认2秒）
        pir_timeout = self.config.get('doorlock', {}).get(
            'package_guard', {}
        ).get('pir_timeout', 2.0)
        
        return check_pir_status(conn, timeout=pir_timeout)
    
    async def _capture_and_analyze(self, device_id: str, session_id: str):
        """拍照并分析威胁等级
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
        """
        try:
            # TODO: 调用ESP32拍照（需要集成ESP32通信模块）
            # current_image = await self._request_photo(device_id)
            
            # 临时：模拟拍照
            logger.bind(tag=TAG).debug(
                f"拍照（模拟）: device_id={device_id}, session_id={session_id}"
            )
            current_image = None
            
            if current_image is None:
                logger.bind(tag=TAG).warning(
                    f"拍照失败，跳过本次分析: device_id={device_id}"
                )
                return
            
            # 加载基准图片
            baseline_image = await self._load_baseline_image(device_id)
            
            if baseline_image is None:
                logger.bind(tag=TAG).warning(
                    f"基准图片不存在，跳过本次分析: device_id={device_id}"
                )
                return
            
            # 调用VLLM分析
            analysis_result = await self._analyze_with_vllm(
                device_id,
                current_image,
                baseline_image
            )
            
            if analysis_result:
                # 处理分析结果
                await self._handle_analysis_result(
                    device_id,
                    session_id,
                    analysis_result
                )
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"拍照分析异常: device_id={device_id}, session_id={session_id}, error={e}"
            )
    
    async def _load_baseline_image(self, device_id: str) -> Optional[bytes]:
        """加载基准图片
        
        Args:
            device_id: 设备ID
            
        Returns:
            图片数据，失败返回None
        """
        try:
            # 先检查缓存
            if device_id in self._baseline_cache:
                return self._baseline_cache[device_id]
            
            # 从数据库获取路径
            config = await self.db.get_config(device_id)
            
            if not config.package_baseline_image:
                return None
            
            # 读取文件
            if os.path.exists(config.package_baseline_image):
                with open(config.package_baseline_image, 'rb') as f:
                    image_data = f.read()
                
                # 更新缓存
                self._baseline_cache[device_id] = image_data
                
                return image_data
            else:
                logger.bind(tag=TAG).warning(
                    f"基准图片文件不存在: device_id={device_id}, "
                    f"path={config.package_baseline_image}"
                )
                return None
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"加载基准图片异常: device_id={device_id}, error={e}"
            )
            return None
    
    async def _analyze_with_vllm(
        self,
        device_id: str,
        current_image: bytes,
        baseline_image: bytes
    ) -> Optional[dict]:
        """使用VLLM分析威胁等级
        
        Args:
            device_id: 设备ID
            current_image: 当前图片
            baseline_image: 基准图片
            
        Returns:
            分析结果字典，包含 threat_level, action, description
        """
        try:
            # 将图片转换为base64
            current_base64 = base64.b64encode(current_image).decode('utf-8')
            baseline_base64 = base64.b64encode(baseline_image).decode('utf-8')
            
            # 构建提示词（从配置文件加载）
            # TODO: 从 doorlock_prompts.yaml 加载提示词
            question = f"""
            请对比当前图片和基准图片，判断门口快递的状态变化和威胁等级。
            
            基准图片：{baseline_base64[:50]}...
            当前图片：{current_base64[:50]}...
            
            请调用 report_package_status 工具报告情况。
            """
            
            # 调用VLLM（需要支持工具调用）
            # TODO: 实现VLLM工具调用集成
            logger.bind(tag=TAG).debug(
                f"调用VLLM分析（模拟）: device_id={device_id}"
            )
            
            # 临时：返回模拟结果
            return {
                "threat_level": "low",
                "action": "passing",
                "description": "路人经过"
            }
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"VLLM分析异常: device_id={device_id}, error={e}"
            )
            return None
    
    async def _handle_analysis_result(
        self,
        device_id: str,
        session_id: str,
        result: dict
    ):
        """处理分析结果并执行威胁响应
        
        Args:
            device_id: 设备ID
            session_id: 会话ID
            result: 分析结果
        """
        try:
            threat_level = result.get('threat_level', 'low')
            action = result.get('action', 'normal')
            description = result.get('description', '')
            
            # 保存警报记录
            alert = PackageAlert(
                device_id=device_id,
                session_id=session_id,
                threat_level=threat_level,
                action=action,
                description=description,
                photo_path="",  # TODO: 保存当前照片
                voice_warning_sent=False,
                notified=False
            )
            
            alert_id = await self.db.save_package_alert(alert)
            
            # 根据威胁等级响应
            if threat_level == "low":
                # 低威胁：不处理
                logger.bind(tag=TAG).debug(
                    f"低威胁，无需处理: device_id={device_id}, action={action}"
                )
                
            elif threat_level == "medium":
                # 中威胁：语音提示 + App通知
                await self._play_voice_warning(
                    device_id,
                    "请问有什么可以帮您？"
                )
                alert.voice_warning_sent = True
                
                await self.notification_service.notify_package_alert(
                    alert_id=alert_id,
                    session_id=session_id,
                    threat_level=threat_level,
                    action=action,
                    description=description,
                    photo_path=alert.photo_path,
                    voice_warning_text="请问有什么可以帮您？"
                )
                alert.notified = True
                
                logger.bind(tag=TAG).info(
                    f"中威胁响应完成: device_id={device_id}, action={action}"
                )
                
            elif threat_level == "high":
                # 高威胁：语音警告 + App通知
                await self._play_voice_warning(
                    device_id,
                    "您的行为已被记录，请立即停止"
                )
                alert.voice_warning_sent = True
                
                await self.notification_service.notify_package_alert(
                    alert_id=alert_id,
                    session_id=session_id,
                    threat_level=threat_level,
                    action=action,
                    description=description,
                    photo_path=alert.photo_path,
                    voice_warning_text="您的行为已被记录，请立即停止"
                )
                alert.notified = True
                
                logger.bind(tag=TAG).warning(
                    f"高威胁响应完成: device_id={device_id}, action={action}"
                )
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"处理分析结果异常: device_id={device_id}, session_id={session_id}, error={e}"
            )
    
    async def _play_voice_warning(self, device_id: str, text: str):
        """播放语音警告
        
        Args:
            device_id: 设备ID
            text: 警告文本
        """
        try:
            # TODO: 集成TTS服务播放语音
            logger.bind(tag=TAG).info(
                f"播放语音警告（模拟）: device_id={device_id}, text={text}"
            )
            
        except Exception as e:
            logger.bind(tag=TAG).error(
                f"播放语音警告异常: device_id={device_id}, text={text}, error={e}"
            )
