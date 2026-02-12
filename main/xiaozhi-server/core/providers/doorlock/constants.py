"""
智能门锁AI常量定义
"""

# 消息类型常量
class MessageType:
    """App通信消息类型"""
    
    # 访客意图识别结果通知
    VISITOR_INTENT = "doorlock_visitor_intent"
    
    # 快递警报通知
    PACKAGE_ALERT = "doorlock_package_alert"
    
    # 看护状态变化通知
    PACKAGE_GUARD_STATUS = "doorlock_package_guard_status"


# 意图类型常量
class IntentType:
    """访客意图类型"""
    
    DELIVERY = "delivery"      # 送快递/外卖
    VISIT = "visit"            # 拜访
    SALES = "sales"            # 推销
    MAINTENANCE = "maintenance"  # 维修/物业
    OTHER = "other"            # 其他


# 威胁等级常量
class ThreatLevel:
    """快递威胁等级"""
    
    LOW = "low"        # 低威胁
    MEDIUM = "medium"  # 中威胁
    HIGH = "high"      # 高威胁


# 行为类型常量
class ActionType:
    """快递相关行为类型"""
    
    TAKING = "taking"      # 拿走
    SEARCHING = "searching"  # 翻找
    DAMAGING = "damaging"   # 破坏
    NORMAL = "normal"      # 正常
    PASSING = "passing"    # 路过
