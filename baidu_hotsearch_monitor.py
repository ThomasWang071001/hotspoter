#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度热搜监控脚本
自动获取百度热搜，当有新热搜产生或热搜消失时在桌面右下角显示通知
详细记录所有热搜的出现位次、时间和消失时间
"""

import requests
import json
import time
import os
import sys
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple

# 桌面通知库
try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

try:
    from win10toast import ToastNotifier
    HAS_WIN10TOAST = True
except ImportError:
    HAS_WIN10TOAST = False

try:
    import pynotifier
    HAS_PYNOTIFIER = True
except ImportError:
    HAS_PYNOTIFIER = False


class HotSearchTracker:
    """
    热搜追踪器 - 追踪每条热搜的出现位次、时间等信息
    """
    
    def __init__(self, script_dir: str):
        self.script_dir = script_dir
        
        # 热搜编号计数器
        self.next_id = 1
        
        # 当前在榜热搜 {title: HotSearchItem}
        self.active_hotsearch: Dict[str, dict] = {}
        
        # 所有历史热搜 {title: HotSearchItem}（包含已消失的）
        self.all_hotsearch: Dict[str, dict] = {}
        
        # 数据文件
        self.data_file = os.path.join(script_dir, "hotsearch_data.json")
        
        # 日志文件
        self.log_file = os.path.join(script_dir, "hotsearch_record.txt")
        
        # 加载数据
        self._load_data()
    
    def _load_data(self):
        """加载保存的数据"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.next_id = data.get('next_id', 1)
                    self.all_hotsearch = data.get('all_hotsearch', {})
                    self.active_hotsearch = data.get('active_hotsearch', {})
                print(f"✓ 已加载历史数据，共记录 {len(self.all_hotsearch)} 条热搜")
            except Exception as e:
                print(f"⚠ 加载数据失败: {e}")
    
    def _save_data(self):
        """保存数据到文件"""
        try:
            data = {
                'next_id': self.next_id,
                'all_hotsearch': self.all_hotsearch,
                'active_hotsearch': self.active_hotsearch,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠ 保存数据失败: {e}")
    
    def update(self, current_list: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        更新热搜状态
        
        Args:
            current_list: 当前热搜列表
            
        Returns:
            (新增热搜列表, 消失热搜列表)
        """
        current_titles = set()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        new_items = []
        disappeared_items = []
        
        # 构建当前热搜字典
        current_dict = {}
        for item in current_list:
            title = item['title']
            if title:
                current_titles.add(title)
                current_dict[title] = item
        
        # 检测消失的热搜
        for title in list(self.active_hotsearch.keys()):
            if title not in current_titles:
                # 热搜消失了
                item = self.active_hotsearch[title]
                item['disappear_time'] = current_time
                item['is_active'] = False
                
                disappeared_items.append(item.copy())
                
                # 更新all_hotsearch中的记录
                if title in self.all_hotsearch:
                    self.all_hotsearch[title]['disappear_time'] = current_time
                    self.all_hotsearch[title]['is_active'] = False
                
                # 从活跃列表移除
                del self.active_hotsearch[title]
        
        # 处理当前热搜（新增或更新）
        for title, item in current_dict.items():
            rank = item.get('rank', 0)
            if rank == 0 and item.get('isTop'):
                rank = 0  # 置顶
            
            if title in self.all_hotsearch:
                # 已存在的热搜，更新位次记录
                old_item = self.all_hotsearch[title]
                
                # 检查这个位次是否已记录过
                if rank not in old_item['ranks']:
                    old_item['ranks'].append(rank)
                    old_item['ranks'].sort()
                
                # 更新最后出现时间
                old_item['last_seen_time'] = current_time
                old_item['is_active'] = True
                
                # 如果之前消失了，现在是重新出现
                if title not in self.active_hotsearch:
                    old_item['reappear_count'] = old_item.get('reappear_count', 0) + 1
                
                # 更新活跃列表
                self.active_hotsearch[title] = old_item.copy()
                
            else:
                # 新热搜
                new_id = self.next_id
                self.next_id += 1
                
                new_item = {
                    'id': new_id,
                    'title': title,
                    'content': title,
                    'first_appear_time': current_time,
                    'last_seen_time': current_time,
                    'disappear_time': None,
                    'ranks': [rank] if rank > 0 or item.get('isTop') else [],
                    'is_active': True,
                    'reappear_count': 0,
                    'hot': item.get('hot', 0),
                    'tag': item.get('newHotName', '') or item.get('hotTag', ''),
                    'desc': item.get('desc', ''),
                    'is_top': item.get('isTop', False)
                }
                
                self.all_hotsearch[title] = new_item
                self.active_hotsearch[title] = new_item.copy()
                new_items.append(new_item.copy())
        
        # 保存数据
        self._save_data()
        
        return new_items, disappeared_items
    
    def get_active_count(self) -> int:
        """获取当前在榜热搜数量"""
        return len(self.active_hotsearch)
    
    def get_total_count(self) -> int:
        """获取历史热搜总数"""
        return len(self.all_hotsearch)
    
    def get_disappeared_count(self) -> int:
        """获取已消失热搜数量"""
        return sum(1 for item in self.all_hotsearch.values() if not item.get('is_active', True))
    
    def format_ranks(self, ranks: List[int]) -> str:
        """格式化排名列表"""
        if not ranks:
            return "无排名记录"
        
        # 排序并去重
        sorted_ranks = sorted(set(ranks))
        result = []
        for r in sorted_ranks:
            if r == 0:
                result.append("置顶位")
            else:
                result.append(f"第{r}位")
        return "、".join(result)
    
    def write_log(self):
        """
        写入日志文件，按用户要求的格式
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"百度热搜监控记录 - 更新于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 80)
        lines.append("")
        
        # 按编号排序获取所有热搜
        sorted_all = sorted(
            self.all_hotsearch.values(),
            key=lambda x: x.get('id', 999999)
        )
        
        # 第一部分：所有出现过的热搜
        lines.append("【所有出现过的热搜】")
        lines.append("-" * 80)
        
        for item in sorted_all:
            id_ = item.get('id', '?')
            first_time = item.get('first_appear_time', '未知')
            ranks = item.get('ranks', [])
            content = item.get('title', '未知')
            is_active = item.get('is_active', True)
            
            ranks_str = self.format_ranks(ranks)
            
            status = "【当前在榜】" if is_active else "【已消失】"
            
            line = f"[{first_time}]{id_}，出现在{ranks_str}，热搜内容：{content} {status}"
            lines.append(line)
        
        lines.append("")
        lines.append("-" * 80)
        lines.append(f"共计 {len(sorted_all)} 条热搜")
        lines.append("")
        
        # 第二部分：消失过的热搜
        disappeared = [item for item in sorted_all if not item.get('is_active', True)]
        
        lines.append("")
        lines.append("【消失过的热搜】")
        lines.append("-" * 80)
        
        for item in disappeared:
            id_ = item.get('id', '?')
            disappear_time = item.get('disappear_time', '未知')
            ranks = item.get('ranks', [])
            content = item.get('title', '未知')
            
            ranks_str = self.format_ranks(ranks)
            
            line = f"[{disappear_time}]{id_}，曾出现于{ranks_str}，热搜内容：{content}"
            lines.append(line)
        
        if disappeared:
            lines.append("")
            lines.append("-" * 80)
            lines.append(f"共计 {len(disappeared)} 条热搜已消失")
        else:
            lines.append("暂无消失的热搜")
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("")
        
        # 写入文件
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
        except Exception as e:
            print(f"⚠ 写入日志失败: {e}")


class BaiduHotSearchMonitor:
    """百度热搜监控器"""
    
    # 百度热搜API
    HOT_SEARCH_URL = "https://top.baidu.com/api/board?platform=wise&tab=realtime"
    
    def __init__(self, check_interval: int = 60, max_notifications: int = 5,
                 notify_disappear: bool = True):
        """
        初始化监控器
        
        Args:
            check_interval: 检查间隔时间（秒），默认60秒
            max_notifications: 每次最多显示的通知数量，默认5条
            notify_disappear: 是否通知热搜消失，默认True
        """
        self.check_interval = check_interval
        self.max_notifications = max_notifications
        self.notify_disappear = notify_disappear
        self.running = False
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 初始化热搜追踪器
        self.tracker = HotSearchTracker(self.script_dir)
        
        # 初始化通知器
        self.toaster = None
        self._init_notifier()
    
    def _init_notifier(self):
        """初始化桌面通知器"""
        if HAS_WIN10TOAST and sys.platform == 'win32':
            self.toaster = ToastNotifier()
            print("✓ 使用 win10toast 进行桌面通知")
        elif HAS_PLYER:
            print("✓ 使用 plyer 进行桌面通知")
        elif HAS_PYNOTIFIER:
            print("✓ 使用 pynotifier 进行桌面通知")
        else:
            print("⚠ 未检测到通知库，将使用系统通知")
    
    def get_hotsearch(self) -> Optional[List[Dict]]:
        """
        获取百度热搜列表
        
        Returns:
            热搜列表，每个元素包含 title, hot, url 等字段
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://top.baidu.com/',
        }
        
        try:
            response = requests.get(self.HOT_SEARCH_URL, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 解析热搜数据 - 新的API格式
            hotsearch_list = []
            
            if data.get('success') and 'data' in data:
                cards = data['data'].get('cards', [])
                for card in cards:
                    if card.get('component') == 'tabTextList':
                        content_list = card.get('content', [])
                        for content_item in content_list:
                            items = content_item.get('content', [])
                            for item in items:
                                hotsearch_item = {
                                    'title': item.get('word', '').strip(),
                                    'hot': item.get('hotScore', 0),
                                    'url': item.get('url', ''),
                                    'desc': item.get('desc', '') or item.get('wordDesc', ''),
                                    'rank': item.get('index', 0),
                                    'rawUrl': item.get('rawUrl', ''),
                                    'isTop': item.get('isTop', False),
                                    'hotTag': item.get('hotTag', ''),
                                    'newHotName': item.get('newHotName', ''),
                                }
                                if hotsearch_item['title']:
                                    hotsearch_list.append(hotsearch_item)
                
                if hotsearch_list:
                    return hotsearch_list
            
            # 尝试旧版API格式
            if data.get('errno') == 0 and 'data' in data:
                content_list = data['data'].get('contentList', [])
                for item in content_list:
                    hotsearch_item = {
                        'title': item.get('word', '').strip(),
                        'hot': item.get('hotScore', 0),
                        'url': item.get('url', ''),
                        'desc': item.get('wordDesc', ''),
                        'rank': item.get('index', 0),
                        'rawUrl': item.get('rawUrl', ''),
                    }
                    if hotsearch_item['title']:
                        hotsearch_list.append(hotsearch_item)
                
                if hotsearch_list:
                    return hotsearch_list
            
            print(f"⚠ API返回数据格式异常")
            return None
            
        except requests.RequestException as e:
            print(f"✗ 网络请求失败: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"✗ JSON解析失败: {e}")
            return None
        except Exception as e:
            print(f"✗ 获取热搜失败: {e}")
            return None
    
    def show_notification(self, title: str, message: str, duration: int = 5):
        """
        显示桌面通知
        
        Args:
            title: 通知标题
            message: 通知内容
            duration: 通知显示时长（秒）
        """
        try:
            if HAS_WIN10TOAST and self.toaster and sys.platform == 'win32':
                self.toaster.show_toast(
                    title,
                    message,
                    icon_path=None,
                    duration=duration,
                    threaded=True
                )
            elif HAS_PLYER:
                notification.notify(
                    title=title,
                    message=message,
                    app_name='百度热搜监控',
                    timeout=duration
                )
            elif HAS_PYNOTIFIER:
                pynotifier.Notification(
                    title,
                    message,
                    duration=duration
                ).send()
            else:
                if sys.platform == 'win32':
                    ps_script = f'''
                    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
                    $template = @"
                    <toast>
                        <visual>
                            <binding template="ToastText02">
                                <text id="1">{title}</text>
                                <text id="2">{message}</text>
                            </binding>
                        </visual>
                    </toast>
"@
                    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
                    $xml.LoadXml($template)
                    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
                    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("百度热搜监控").Show($toast)
                    '''
                    os.system(f'powershell -command "{ps_script}"')
                elif sys.platform == 'darwin':
                    os.system(f'''osascript -e 'display notification "{message}" with title "{title}"' ''')
                else:
                    os.system(f'notify-send "{title}" "{message}"')
                    
        except Exception as e:
            print(f"⚠ 显示通知失败: {e}")
            print(f"\n{'='*50}")
            print(f"📢 {title}")
            print(f"   {message}")
            print(f"{'='*50}\n")
    
    def monitor(self):
        """开始监控热搜变化"""
        print("\n" + "="*60)
        print("🔥 百度热搜监控已启动")
        print(f"   检查间隔: {self.check_interval} 秒")
        print(f"   每次最多通知: {self.max_notifications} 条")
        print(f"   热搜消失通知: {'开启' if self.notify_disappear else '关闭'}")
        print(f"   记录文件: {self.tracker.log_file}")
        print("="*60 + "\n")
        
        # 显示当前统计
        total = self.tracker.get_total_count()
        active = self.tracker.get_active_count()
        disappeared = self.tracker.get_disappeared_count()
        
        if total > 0:
            print(f"📊 历史统计: 共记录 {total} 条热搜")
            print(f"   当前在榜: {active} 条 | 已消失: {disappeared} 条\n")
        
        self.running = True
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # 获取当前热搜
                current_hotsearch = self.get_hotsearch()
                
                if current_hotsearch:
                    # 更新追踪器并获取变化
                    new_items, disappeared_items = self.tracker.update(current_hotsearch)
                    
                    has_changes = bool(new_items or disappeared_items)
                    
                    if has_changes:
                        # 打印变化摘要
                        print(f"\n{'='*60}")
                        print(f"🔔 [{current_time.strftime('%H:%M:%S')}] 热搜榜变化")
                        print(f"    新增: {len(new_items)} 条 | 消失: {len(disappeared_items)} 条")
                        print(f"{'='*60}")
                        
                        # 显示新增热搜
                        if new_items:
                            print(f"\n📥 新增热搜 ({len(new_items)}条):")
                            notify_items = new_items[:self.max_notifications]
                            
                            for item in notify_items:
                                id_ = item.get('id', '?')
                                title_text = f"🔥 新热搜 #{id_}"
                                message = item['title']
                                
                                self.show_notification(title_text, message)
                                
                                ranks = item.get('ranks', [])
                                rank_str = self.tracker.format_ranks(ranks)
                                
                                print(f"  #{id_} {item['title']}")
                                print(f"       首次出现在 {rank_str}")
                                
                                time.sleep(0.3)
                            
                            if len(new_items) > self.max_notifications:
                                remaining = len(new_items) - self.max_notifications
                                print(f"  ... 还有 {remaining} 条新热搜未通知")
                        
                        # 显示消失热搜
                        if disappeared_items and self.notify_disappear:
                            print(f"\n📤 消失热搜 ({len(disappeared_items)}条):")
                            notify_items = disappeared_items[:self.max_notifications]
                            
                            for item in notify_items:
                                id_ = item.get('id', '?')
                                title_text = f"📉 热搜消失 #{id_}"
                                message = item['title']
                                
                                self.show_notification(title_text, message)
                                
                                ranks = item.get('ranks', [])
                                rank_str = self.tracker.format_ranks(ranks)
                                
                                print(f"  #{id_} {item['title']}")
                                print(f"       曾出现于 {rank_str}")
                                
                                time.sleep(0.3)
                            
                            if len(disappeared_items) > self.max_notifications:
                                remaining = len(disappeared_items) - self.max_notifications
                                print(f"  ... 还有 {remaining} 条消失热搜未通知")
                        
                        # 更新日志文件
                        self.tracker.write_log()
                        
                        print(f"\n✓ 记录已更新到: {self.tracker.log_file}")
                        print(f"{'='*60}\n")
                        
                    else:
                        active_count = self.tracker.get_active_count()
                        print(f"[{current_time.strftime('%H:%M:%S')}] 无变化 | 当前在榜: {active_count} 条 | 前3: ", end="")
                        for item in current_hotsearch[:3]:
                            rank = item.get('rank', '?')
                            if item.get('isTop'):
                                rank = '置顶'
                            print(f"#{rank} {item['title'][:8]}...", end=" | ")
                        print()
                else:
                    print(f"[{current_time.strftime('%H:%M:%S')}] ⚠ 获取热搜失败，等待重试...")
                
                # 等待下一次检查
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n\n⏹ 收到停止信号，正在退出...")
                self.running = False
                break
            except Exception as e:
                print(f"✗ 监控出错: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(10)
        
        # 最后更新一次日志
        self.tracker.write_log()
        
        # 显示统计信息
        total = self.tracker.get_total_count()
        disappeared = self.tracker.get_disappeared_count()
        
        print(f"\n📊 本次监控统计:")
        print(f"   共记录 {total} 条热搜")
        print(f"   已消失 {disappeared} 条热搜")
        print(f"   日志文件: {self.tracker.log_file}")
        print("\n👋 百度热搜监控已停止")
    
    def stop(self):
        """停止监控"""
        self.running = False
    
    def show_current_hotsearch(self, count: int = 10):
        """显示当前热搜榜"""
        print(f"\n{'='*60}")
        print(f"🔥 当前百度热搜榜 Top {count}")
        print(f"{'='*60}")
        
        hotsearch = self.get_hotsearch()
        
        if hotsearch:
            for item in hotsearch[:count]:
                rank = item.get('rank', 0)
                title = item['title']
                hot = item.get('hot', 0)
                desc = item.get('desc', '')
                is_top = item.get('isTop', False)
                hot_tag = item.get('newHotName', '') or item.get('hotTag', '')
                
                if is_top:
                    print(f"\n📍 置顶: {title}")
                else:
                    tag_str = f" [{hot_tag}]" if hot_tag else ""
                    print(f"\n{rank:2}. {title}{tag_str}")
                
                if hot > 0:
                    print(f"    🔥 热度: {hot:,}")
                elif not is_top:
                    print(f"    🔥 热度: -")
                    
                if desc:
                    print(f"    📝 {desc[:60]}...")
            
            print(f"\n{'='*60}")
            print(f"   共获取 {len(hotsearch)} 条热搜")
            print(f"{'='*60}")
        else:
            print("⚠ 无法获取热搜数据")
    
    def show_record(self):
        """显示热搜记录"""
        log_file = self.tracker.log_file
        
        print(f"\n{'='*60}")
        print(f"📋 热搜记录")
        print(f"{'='*60}")
        
        if not os.path.exists(log_file):
            print("暂无记录，请先运行监控")
            return
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            print(content)
        except Exception as e:
            print(f"⚠ 读取记录失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='百度热搜监控 - 当有新热搜产生或热搜消失时自动通知，并记录所有热搜的详细信息',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python baidu_hotsearch_monitor.py              # 默认每60秒检查一次
  python baidu_hotsearch_monitor.py -i 30        # 每30秒检查一次
  python baidu_hotsearch_monitor.py --show       # 只显示当前热搜榜
  python baidu_hotsearch_monitor.py --record     # 显示热搜记录
  python baidu_hotsearch_monitor.py --no-disappear  # 关闭热搜消失通知

依赖安装:
  pip install requests plyer        # 跨平台通知
  pip install win10toast            # Windows 10/11 推荐安装

记录文件:
  hotsearch_record.txt - 记录所有热搜的出现位次和时间
  hotsearch_data.json  - 热搜数据文件
        '''
    )
    
    parser.add_argument('-i', '--interval', type=int, default=60,
                        help='检查间隔时间（秒），默认60秒')
    parser.add_argument('-n', '--notifications', type=int, default=5,
                        help='每次最多显示的通知数量，默认5条')
    parser.add_argument('--no-disappear', action='store_true',
                        help='关闭热搜消失通知')
    parser.add_argument('--show', action='store_true',
                        help='只显示当前热搜榜，不监控')
    parser.add_argument('--record', action='store_true',
                        help='显示热搜记录')
    parser.add_argument('--count', type=int, default=20,
                        help='显示数量（配合--show使用），默认20')
    
    args = parser.parse_args()
    
    monitor = BaiduHotSearchMonitor(
        check_interval=args.interval,
        max_notifications=args.notifications,
        notify_disappear=not args.no_disappear
    )
    
    if args.show:
        monitor.show_current_hotsearch(args.count)
    elif args.record:
        monitor.show_record()
    else:
        try:
            monitor.monitor()
        except KeyboardInterrupt:
            monitor.stop()


if __name__ == '__main__':
    main()
