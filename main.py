from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import pymysql
from pymysql.cursors import DictCursor
import re

@register("lmgames", "author", "测试端插件")

class DatabasePlugin:
    def __init__(self, config):
        """
        初始化数据库连接
        config: 包含数据库连接信息的字典
        """
        self.db_config = {
            'host': config.get('host', 'localhost'),
            'port': config.get('port', 3306),
            'user': config.get('user', 'root'),
            'password': config.get('password', ''),
            'db': config.get('database', ''),
            'charset': 'utf8mb4',
            'cursorclass': DictCursor
        }
        self.connect()

    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(**self.db_config)
            print("数据库连接成功")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            raise

    def execute_query(self, query, params=None, fetch_one=False):
        """执行SQL查询"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                if fetch_one:
                    result = cursor.fetchone()
                else:
                    result = cursor.fetchall()
                self.connection.commit()
                return result
        except Exception as e:
            print(f"查询执行失败: {e}")
            self.connection.rollback()
            return None

    def execute_update(self, query, params=None):
        """执行SQL更新操作"""
        try:
            with self.connection.cursor() as cursor:
                result = cursor.execute(query, params)
                self.connection.commit()
                return result
        except Exception as e:
            print(f"更新执行失败: {e}")
            self.connection.rollback()
            return None

    def extract_steamid(self, message):
        """
        从消息中提取SteamID
        假设消息格式为: "绑定 STEAM_ID"
        """
        # 使用正则表达式提取可能的SteamID
        # SteamID通常是一串数字，或者是STEAM_X:Y:Z格式
        patterns = [
            r'STEAM_[0-5]:[01]:\d+',  # STEAM_X:Y:Z格式
            r'7656119\d{10}',  # 64位SteamID
            r'绑定\s+(\S+)'  # 绑定命令后的任何非空白字符
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                # 如果是最后一个模式，返回捕获组
                if pattern == r'绑定\s+(\S+)':
                    return match.group(1)
                return match.group(0)
        
        return None

    def bind_steamid(self, message, qq_number):
        """
        绑定SteamID到QQ号
        """
        # 从消息中提取steamid
        steamid = self.extract_steamid(message)
        if not steamid:
            return "未找到有效的SteamID，请使用格式: 绑定 STEAM_ID"
        
        # 检查steamid是否存在
        check_query = "SELECT * FROM robot WHERE steamId = %s"
        user_record = self.execute_query(check_query, (steamid,), fetch_one=True)
        
        if not user_record:
            return "你还没有进入过游戏里,请进入游戏后再开户吧！"
        
        # 检查是否已经绑定过
        if user_record.get('QQ'):
            return "该SteamID已经绑定过QQ号了！"
        
        # 更新QQ号
        update_query = "UPDATE robot SET QQ = %s WHERE steamId = %s"
        self.execute_update(update_query, (qq_number, steamid))
        
        # 检查经济账户是否存在
        economy_check = "SELECT * FROM uconomy WHERE steamId = %s"
        economy_record = self.execute_query(economy_check, (steamid,), fetch_one=True)
        
        if economy_record:
            # 更新余额
            update_balance = "UPDATE uconomy SET balance = balance + 20000 WHERE steamId = %s"
            self.execute_update(update_balance, (steamid,))
            new_balance = economy_record['balance'] + 20000
        else:
            # 创建新经济账户
            create_account = "INSERT INTO uconomy (steamId, balance) VALUES (%s, 20000)"
            self.execute_update(create_account, (steamid,))
            new_balance = 20000
        
        return f"绑定成功！已奖励20000游戏币，当前余额: {new_balance}"

    def daily_check_in(self, qq_number):
        """
        每日签到功能
        """
        # 通过QQ号获取steamId
        get_steamid_query = "SELECT steamId FROM robot WHERE QQ = %s"
        user_record = self.execute_query(get_steamid_query, (qq_number,), fetch_one=True)
        
        if not user_record:
            return "请先绑定SteamID后再签到！"
        
        steamid = user_record['steamId']
        
        # 检查经济账户
        economy_check = "SELECT * FROM uconomy WHERE steamId = %s"
        economy_record = self.execute_query(economy_check, (steamid,), fetch_one=True)
        
        # 签到奖励
        reward = 1000  # 每日签到奖励1000游戏币
        
        if economy_record:
            # 更新余额
            update_balance = "UPDATE uconomy SET balance = balance + %s WHERE steamId = %s"
            self.execute_update(update_balance, (reward, steamid))
            new_balance = economy_record['balance'] + reward
        else:
            # 创建新经济账户
            create_account = "INSERT INTO uconomy (steamId, balance) VALUES (%s, %s)"
            self.execute_update(create_account, (steamid, reward))
            new_balance = reward
        
        return f"签到成功！获得{reward}游戏币，当前余额: {new_balance}"

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'connection'):
            self.connection.close()

# 使用示例
if __name__ == "__main__":
    # 数据库配置
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'your_username',
        'password': 'your_password',
        'database': 'your_database'
    }
    
    # 创建插件实例
    plugin = DatabasePlugin(db_config)
    
    try:
        # 绑定SteamID示例
        result = plugin.bind_steamid("绑定 STEAM_1:1:123456", "123456789")
        print(result)
        
        # 签到示例
        result = plugin.daily_check_in("123456789")
        print(result)
    finally:
        # 关闭连接
        plugin.close()
from database_plugin import DatabasePlugin

# 初始化插件
db_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'your_username',
    'password': 'your_password',
    'database': 'your_database'
}

db_plugin = DatabasePlugin(db_config)

# 注册命令处理函数
@filter.command("绑定")
async def bind_steamid(event):
    message = event.message
    qq_number = event.sender.id  # 根据你的框架获取QQ号
    
    result = db_plugin.bind_steamid(message, qq_number)
    await event.reply(result)

@filter.command("签到")
async def daily_check_in(event):
    qq_number = event.sender.id  # 根据你的框架获取QQ号
    
    result = db_plugin.daily_check_in(qq_number)
    await event.reply(result)