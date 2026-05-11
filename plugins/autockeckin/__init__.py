import re
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import schemas
from app.chain.site import SiteChain
from app.core.config import settings
from app.core.event import EventManager, Event
from app.db.site_oper import SiteOper
from app.helper.sites import SitesHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType
from app.utils.http import RequestUtils
from app.utils.site import SiteUtils


class AutoCkeckin(_PluginBase):
    """
    PT站点自动签到插件（简化版）
    支持 NexusPHP、Gazelle 等主流站点框架
    """

    # 插件名称
    plugin_name = "站点自动签到"
    # 插件描述
    plugin_desc = "自动签到MoviePilot中配置的所有PT站点，支持NexusPHP等主流框架。"
    # 插件图标
    plugin_icon = "checkin.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "xl-jeeter"
    # 作者主页
    author_url = "https://github.com/xl-jeeter"
    # 插件配置项ID前缀
    plugin_config_prefix = "autockeckin_"
    # 加载顺序
    plugin_order = 15
    # 可使用的用户级别
    auth_level = 1

    # 依赖
    sites: SitesHelper = None
    siteoper: SiteOper = None
    sitechain: SiteChain = None
    event: EventManager = None

    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None

    # 配置属性
    _enabled: bool = False
    _cron: str = "0 8 * * *"
    _onlyonce: bool = False
    _notify: bool = True
    _exclude_sites: str = ""

    def init_plugin(self, config: dict = None):
        self.sites = SitesHelper()
        self.siteoper = SiteOper()

        # 停止现有任务
        self.stop_service()

        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron", "0 8 * * *")
            self._notify = config.get("notify", True)
            self._onlyonce = config.get("onlyonce")
            self._exclude_sites = config.get("exclude_sites", "")

        # 立即运行一次
        if self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            logger.info("站点自动签到服务启动，立即运行一次")
            self._scheduler.add_job(
                func=self.sign_in,
                trigger="date",
                run_date=datetime.now(tz=pytz.timezone(settings.TZ))
                + timedelta(seconds=3),
                name="站点自动签到",
            )
            # 关闭一次性开关
            self._onlyonce = False
            self.update_config(
                {
                    "enabled": self._enabled,
                    "cron": self._cron,
                    "notify": self._notify,
                    "onlyonce": False,
                    "exclude_sites": self._exclude_sites,
                }
            )

            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/site_checkin",
                "event": "PluginAction",
                "desc": "站点签到",
                "category": "站点",
                "data": {"action": "site_checkin"},
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/checkin",
                "endpoint": self.api_checkin,
                "methods": ["GET"],
                "summary": "站点签到",
                "description": "手动触发所有站点签到",
            }
        ]

    def api_checkin(self, apikey: str) -> schemas.Response:
        """API调用签到"""
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        results = self.sign_in()
        return schemas.Response(
            success=True, message=f"签到完成，共处理 {len(results)} 个站点"
        )

    def get_service(self) -> List[Dict[str, Any]]:
        """注册插件公共服务"""
        if self._enabled and self._cron:
            try:
                return [
                    {
                        "id": "AutoCkeckin",
                        "name": "站点自动签到服务",
                        "trigger": CronTrigger.from_crontab(self._cron),
                        "func": self.sign_in,
                        "kwargs": {},
                    }
                ]
            except Exception as err:
                logger.error(f"定时任务配置错误：{str(err)}")
        return []

    def sign_in(self, event: Event = None):
        """
        自动签到主逻辑
        """
        if event:
            event_data = event.event_data
            if not event_data or event_data.get("action") != "site_checkin":
                return

        logger.info("========== 开始站点自动签到 ==========")

        # 获取所有站点
        all_sites = [
            site for site in self.sites.get_indexers() if not site.get("public")
        ]
        if not all_sites:
            logger.warning("未获取到站点列表")
            return []

        # 解析排除站点
        exclude_list = [
            s.strip() for s in self._exclude_sites.split(",") if s.strip()
        ]

        # 过滤站点
        do_sites = [s for s in all_sites if s.get("name") not in exclude_list]
        logger.info(f"共 {len(do_sites)} 个站点需要签到（排除 {len(exclude_list)} 个）")

        # 执行签到
        results = []
        for site_info in do_sites:
            site_name = site_info.get("name", "")
            try:
                state, message = self.__signin_site(site_info)
                status = "✅" if state else "❌"
                results.append((site_name, status, message))
                logger.info(f"{status} {site_name} - {message}")
            except Exception as e:
                results.append((site_name, "❌", f"签到异常: {str(e)[:50]}"))
                logger.error(f"❌ {site_name} 签到异常: {str(e)}")

        # 统计
        ok_count = sum(1 for _, s, _ in results if s == "✅")
        fail_count = sum(1 for _, s, _ in results if s == "❌")
        summary = f"签到完成: ✅成功{ok_count} ❌失败{fail_count} / 共{len(results)}站"
        logger.info(f"========== {summary} ==========")

        # 保存签到记录
        today_key = f"{datetime.now().month}月{datetime.now().day}日"
        self.save_data(
            today_key,
            [
                {"site": name, "status": f"{status} {detail}"}
                for name, status, detail in results
            ],
        )

        # 发送通知
        if self._notify:
            detail_text = "\n".join(
                [f"  {s} {n} - {d}" for n, s, d in results]
            )
            self.post_message(
                mtype=NotificationType.SiteMessage,
                title="【站点自动签到完成】",
                text=f"{summary}\n\n{detail_text}",
            )

        return results

    def __signin_site(self, site_info: dict) -> Tuple[bool, str]:
        """
        签到单个站点
        """
        site_name = site_info.get("name", "")
        site_url = site_info.get("url", "")
        site_cookie = site_info.get("cookie", "")
        ua = site_info.get("ua", "")
        render = site_info.get("render", False)
        proxies = settings.PROXY if site_info.get("proxy") else None
        proxy_server = settings.PROXY_SERVER if site_info.get("proxy") else None

        if not site_url or not site_cookie:
            return False, "未配置地址或Cookie"

        # 构建签到URL
        checkin_url = urljoin(site_url, "attendance.php")

        try:
            if render:
                # 浏览器仿真模式
                from app.helper.browser import PlaywrightHelper
                from app.helper.cloudflare import under_challenge

                page_source = PlaywrightHelper().get_page_source(
                    url=checkin_url,
                    cookies=site_cookie,
                    ua=ua,
                    proxies=proxy_server,
                )
                if not SiteUtils.is_logged_in(page_source):
                    if under_challenge(page_source):
                        return False, "Cloudflare拦截"
                    return False, "Cookie已失效"
                else:
                    if re.search(r"已签|签到已得", page_source, re.IGNORECASE):
                        return True, "今日已签到"
                    return True, "签到成功（仿真）"
            else:
                # HTTP请求模式
                res = RequestUtils(
                    cookies=site_cookie, ua=ua, proxies=proxies
                ).get_res(url=checkin_url)

                if not res:
                    # 尝试访问首页
                    res = RequestUtils(
                        cookies=site_cookie, ua=ua, proxies=proxies
                    ).get_res(url=site_url)

                if res and res.status_code in [200, 500, 403]:
                    if not SiteUtils.is_logged_in(res.text):
                        from app.helper.cloudflare import under_challenge

                        if under_challenge(res.text):
                            return False, "Cloudflare拦截"
                        elif res.status_code == 200:
                            return False, "Cookie已失效"
                        else:
                            return False, f"状态码: {res.status_code}"
                    else:
                        # 已登录，检查是否已签到
                        if re.search(
                            r"已签到|已经签到|签到成功|签到已得",
                            res.text,
                            re.IGNORECASE,
                        ):
                            return True, "今日已签到"
                        return True, "签到成功"
                elif res is not None:
                    return False, f"状态码: {res.status_code}"
                else:
                    return False, "无法打开网站"

        except Exception as e:
            logger.warn(f"{site_name} 签到失败：{str(e)}")
            traceback.print_exc()
            return False, f"签到失败: {str(e)[:50]}"

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面
        """
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify",
                                            "label": "开启通知",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "onlyonce",
                                            "label": "立即运行一次",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cron",
                                            "label": "签到周期（Cron表达式）",
                                            "placeholder": "0 8 * * *",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "exclude_sites",
                                            "label": "排除站点（逗号分隔站点名称）",
                                            "placeholder": "馒头,北洋园",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "签到周期使用cron表达式，默认每天8点签到（0 8 * * *）。支持NexusPHP等主流站点框架。对于需要验证码的站点（如北洋园），建议排除后手动签到。",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "cron": "0 8 * * *",
            "notify": True,
            "onlyonce": False,
            "exclude_sites": "",
        }

    def get_page(self) -> List[dict]:
        """
        拼装插件详情页面
        """
        # 获取今天的签到数据
        today_key = f"{datetime.now().month}月{datetime.now().day}日"
        sign_data = self.get_data(today_key)

        if sign_data and isinstance(sign_data, list):
            contents = [
                {
                    "component": "tr",
                    "props": {"class": "text-sm"},
                    "content": [
                        {
                            "component": "td",
                            "props": {
                                "class": "whitespace-nowrap break-keep text-high-emphasis"
                            },
                            "text": data.get("site", ""),
                        },
                        {
                            "component": "td",
                            "text": data.get("status", ""),
                        },
                    ],
                }
                for data in sign_data
            ]
        else:
            contents = [
                {
                    "component": "tr",
                    "props": {"class": "text-sm"},
                    "content": [
                        {
                            "component": "td",
                            "props": {"colspan": 2, "class": "text-center"},
                            "text": "暂无签到数据",
                        }
                    ],
                }
            ]

        return [
            {
                "component": "VTable",
                "props": {"hover": True},
                "content": [
                    {
                        "component": "thead",
                        "content": [
                            {
                                "component": "th",
                                "props": {"class": "text-start ps-4"},
                                "text": "站点",
                            },
                            {
                                "component": "th",
                                "props": {"class": "text-start ps-4"},
                                "text": "状态",
                            },
                        ],
                    },
                    {"component": "tbody", "content": contents},
                ],
            }
        ]

    def stop_service(self):
        """退出插件"""
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("退出插件失败：%s" % str(e))
