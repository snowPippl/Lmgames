from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import pymysql
from pymysql.cursors import DictCursor
import re
# 尝试导入 AstrBot 的注册函数和过滤器
@register("lmgamse", "author", "测试插件", "1.0.0", "repo url")
class LMGamesPlugin:
    def __init__(self, bot, config):
        """
        初始化插件
        """
        self.bot = bot
        self.config = config
        
        # 数据库配置
        self.db_config = {
            'host': config.get('db_host', 'localhost'),
            'port': config.get('db_port', 3306),
            'user': config.get('db_user', 'root'),
            'password': config.get('db_password', ''),
            'db': config.get('db_name', ''),
            'charset': 'utf8mb4',
            'cursorclass': DictCursor
        }
        
        # 连接数据库
        self.connection = None
        self.connect()
        
        # 注册命令
        self.register_commands()

    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(**self.db_config)
            print("数据库连接成功")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            self.connection = None

    def execute_query(self, query, params=None, fetch_one=False):
        """执行SQL查询"""
        if not self.connection:
            self.connect()
            if not self.connection:
                return None
                
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
            if self.connection:
                self.connection.rollback()
            return None

    def execute_update(self, query, params=None):
        """执行SQL更新操作"""
        if not self.connection:
            self.connect()
            if not self.connection:
                return None
                
        try:
            with self.connection.cursor() as cursor:
                result = cursor.execute(query, params)
                self.connection.commit()
                return result
        except Exception as e:
            print(f"更新执行失败: {e}")
            if self.connection:
                self.connection.rollback()
            return None

    def extract_steamid(self, message):
        """
        从消息中提取SteamID
        假设消息格式为: "绑定 STEAM_ID"
        """
        # 使用正则表达式提取可能的SteamID
        patterns = [
            r'STEAM_[0-5]:[01]:\d+',  # STEAM_X:Y:Z格式
            r'7656119\d{10}',  # 64位SteamID
            r'绑定\s+(\S+)'  # 绑定命令后的任何非空白字符
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                if pattern == r'绑定\s+(\S+)':
                    return match.group(1)
                return match.group(0)
        
        return None

    async def bind_steamid(self, event):
        """
        绑定SteamID到QQ号
        """
        message = event.message
        qq_number = str(event.sender.id)
        
        # 从消息中提取steamid
        steamid = self.extract_steamid(message)
        if not steamid:
            await event.reply("未找到有效的SteamID，请使用格式: 绑定 STEAM_ID")
            return
        
        # 检查steamid是否存在
        check_query = "SELECT * FROM robot WHERE steamId = %s"
        user_record = self.execute_query(check_query, (steamid,), fetch_one=True)
        
        if not user_record:
            await event.reply("你还没有进入过游戏里,请进入游戏后再开户吧！")
            return
        
        # 检查是否已经绑定过
        if user_record.get('QQ'):
            await event.reply("该SteamID已经绑定过QQ号了！")
            return
        
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
        
        await event.reply(f"绑定成功！已奖励20000游戏币，当前余额: {new_balance}")

    async def daily_check_in(self, event):
        """
        每日签到功能
        """
        qq_number = str(event.sender.id)
        
        # 通过QQ号获取steamId
        get_steamid_query = "SELECT steamId FROM robot WHERE QQ = %s"
        user_record = self.execute_query(get_steamid_query, (qq_number,), fetch_one=True)
        
        if not user_record:
            await event.reply("请先绑定SteamID后再签到！")
            return
        
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
        
        await event.reply(f"签到成功！获得{reward}游戏币，当前余额: {new_balance}")

    def register_commands(self):
        """使用 @filter.command 注册命令"""
        # 绑定命令
        @filter.command("绑定")
        async def bind_handler(event):
            await self.bind_steamid(event)

        # 签到命令
        @filter.command("签到")
        async def checkin_handler(event):
            await self.daily_check_in(event)

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()

# 插件加载时调用的函数
def setup(bot, config):
    plugin = LMGamesPlugin(bot, config)
    return plugin