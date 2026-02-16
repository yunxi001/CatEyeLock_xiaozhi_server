"""
验证门锁AI提示词配置

检查项：
1. YAML语法正确性
2. 必需字段完整性
3. 提示词内容有效性
4. 工具函数定义完整性
5. 示例场景覆盖度
"""
import yaml
from pathlib import Path
from loguru import logger

TAG = "PromptVerification"


def verify_prompts():
    """验证提示词配置"""
    config_path = Path("config/doorlock_prompts.yaml")
    
    if not config_path.exists():
        logger.bind(tag=TAG).error(f"配置文件不存在: {config_path}")
        return False
    
    try:
        # 1. 加载YAML配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logger.bind(tag=TAG).info("✓ YAML语法验证通过")
        
        # 2. 检查必需字段
        required_fields = [
            'intent_recognition_prompt',
            'package_guard_prompt',
            'welcome_templates',
            'default_greeting'
        ]
        
        for field in required_fields:
            if field not in config:
                logger.bind(tag=TAG).error(f"✗ 缺少必需字段: {field}")
                return False
        
        logger.bind(tag=TAG).info("✓ 必需字段完整性检查通过")
        
        # 3. 验证意图识别提示词
        intent_prompt = config['intent_recognition_prompt']
        intent_keywords = [
            '系统角色',
            '职责说明',
            '对话风格',
            '对话策略',
            '工具调用',
            'enable_package_guard',
            'disable_package_guard',
            'update_package_baseline',
            'report_package_status',
            '示例对话'
        ]
        
        missing_keywords = []
        for keyword in intent_keywords:
            if keyword not in intent_prompt:
                missing_keywords.append(keyword)
        
        if missing_keywords:
            logger.bind(tag=TAG).warning(f"意图识别提示词缺少关键词: {missing_keywords}")
        else:
            logger.bind(tag=TAG).info("✓ 意图识别提示词内容完整")
        
        # 4. 验证看护模式提示词
        guard_prompt = config['package_guard_prompt']
        guard_keywords = [
            '看护任务',
            '威胁等级',
            '低威胁',
            '中威胁',
            '高威胁',
            'is_owner',
            '行为类型',
            'taking',
            'searching',
            'damaging',
            'normal',
            'passing',
            '工具调用',
            '基准图片',
            '示例场景'
        ]
        
        missing_guard_keywords = []
        for keyword in guard_keywords:
            if keyword not in guard_prompt:
                missing_guard_keywords.append(keyword)
        
        if missing_guard_keywords:
            logger.bind(tag=TAG).warning(f"看护模式提示词缺少关键词: {missing_guard_keywords}")
        else:
            logger.bind(tag=TAG).info("✓ 看护模式提示词内容完整")
        
        # 5. 验证欢迎词模板
        templates = config['welcome_templates']
        
        if not isinstance(templates, list) or len(templates) < 3:
            logger.bind(tag=TAG).error("✗ 欢迎词模板数量不足（至少需要3个风格）")
            return False
        
        # 检查必需的风格
        template_names = [t['name'] for t in templates]
        required_styles = ['温馨家庭', '简洁风格', '正式风格']
        
        for style in required_styles:
            if style not in template_names:
                logger.bind(tag=TAG).error(f"✗ 缺少必需的欢迎词风格: {style}")
                return False
        
        logger.bind(tag=TAG).info(f"✓ 欢迎词模板完整（共{len(templates)}个风格）")
        
        # 6. 验证欢迎词占位符
        for template in templates:
            for time_slot in ['morning', 'afternoon', 'evening', 'night', 'default']:
                if time_slot in template:
                    greeting = template[time_slot]
                    if '{name}' not in greeting:
                        logger.bind(tag=TAG).warning(
                            f"欢迎词模板 {template['name']}.{time_slot} 缺少 {{name}} 占位符"
                        )
        
        logger.bind(tag=TAG).info("✓ 欢迎词占位符检查完成")
        
        # 7. 验证默认欢迎词
        default_greeting = config['default_greeting']
        required_time_slots = ['morning', 'afternoon', 'evening', 'night', 'default']
        
        for slot in required_time_slots:
            if slot not in default_greeting:
                logger.bind(tag=TAG).error(f"✗ 默认欢迎词缺少时段: {slot}")
                return False
        
        logger.bind(tag=TAG).info("✓ 默认欢迎词完整")
        
        # 8. 统计示例场景数量
        intent_examples = intent_prompt.count('场景')
        guard_examples = guard_prompt.count('场景')
        
        logger.bind(tag=TAG).info(f"意图识别示例场景数量: {intent_examples}")
        logger.bind(tag=TAG).info(f"看护模式示例场景数量: {guard_examples}")
        
        if intent_examples < 3:
            logger.bind(tag=TAG).warning("意图识别示例场景不足3个")
        
        if guard_examples < 5:
            logger.bind(tag=TAG).warning("看护模式示例场景不足5个")
        
        # 9. 验证工具函数定义
        tools_in_intent = [
            'enable_package_guard',
            'disable_package_guard',
            'update_package_baseline'
        ]
        
        tools_in_guard = [
            'report_package_status',
            'update_package_baseline',
            'enable_package_guard',
            'disable_package_guard'
        ]
        
        for tool in tools_in_intent:
            if tool not in intent_prompt:
                logger.bind(tag=TAG).error(f"✗ 意图识别提示词缺少工具: {tool}")
                return False
        
        for tool in tools_in_guard:
            if tool not in guard_prompt:
                logger.bind(tag=TAG).error(f"✗ 看护模式提示词缺少工具: {tool}")
                return False
        
        logger.bind(tag=TAG).info("✓ 工具函数定义完整")
        
        # 10. 验证欢迎词长度
        max_length = 20
        long_greetings = []
        
        for template in templates:
            for time_slot in ['morning', 'afternoon', 'evening', 'night', 'default']:
                if time_slot in template:
                    greeting = template[time_slot].replace('{name}', '张三')
                    if len(greeting) > max_length:
                        long_greetings.append(f"{template['name']}.{time_slot}: {len(greeting)}字")
        
        if long_greetings:
            logger.bind(tag=TAG).warning(f"以下欢迎词超过{max_length}字: {long_greetings}")
        else:
            logger.bind(tag=TAG).info(f"✓ 所有欢迎词长度符合要求（<{max_length}字）")
        
        # 验证通过
        logger.bind(tag=TAG).success("=" * 50)
        logger.bind(tag=TAG).success("提示词配置验证通过！")
        logger.bind(tag=TAG).success("=" * 50)
        
        return True
        
    except yaml.YAMLError as e:
        logger.bind(tag=TAG).error(f"YAML解析错误: {e}")
        return False
    except Exception as e:
        logger.bind(tag=TAG).error(f"验证过程出错: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    success = verify_prompts()
    sys.exit(0 if success else 1)
