"""
疫苗提醒业务常量
所有阈值、规则都集中在这里，后续改 30 天、7 天、1 天这些参数只动这一个文件。
"""

# 默认查询「未来多少天内到期」—— 用于 GET /due 的默认值和定时任务默认扫描范围
DEFAULT_WITHIN_DAYS = 30

# 紧急阈值：距离到期 ≤ 这个天数的算「即将到期 / 需要重点关注」，用在 stats 的 expiring_in_7_days
URGENT_WITHIN_DAYS = 7

# 生成提醒记录时默认通知渠道
DEFAULT_REMINDER_CHANNEL = "manual"

# 提醒记录去重时视为「仍在处理中」的状态，避免重复生成
ACTIVE_REMINDER_STATUSES = ("pending", "notified")

# 单次扫描最大允许 within_days（防 SQL 性能问题）
MAX_WITHIN_DAYS = 365

# 单次扫描最小 within_days
MIN_WITHIN_DAYS = 1
