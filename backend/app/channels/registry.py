from app.channels.base import BaseChannelAdapter
from app.channels.dingtalk import DingTalkChannelAdapter
from app.channels.feishu import FeishuChannelAdapter
from app.channels.rest_api import RestAPIChannelAdapter
from app.channels.wecom import WeComChannelAdapter
from app.channels.web_widget import WebWidgetChannelAdapter
from app.schemas.channel import ChannelType

_ADAPTERS: dict[ChannelType, BaseChannelAdapter] = {
    ChannelType.WECOM: WeComChannelAdapter(),
    ChannelType.DINGTALK: DingTalkChannelAdapter(),
    ChannelType.FEISHU: FeishuChannelAdapter(),
    ChannelType.WEB_WIDGET: WebWidgetChannelAdapter(),
    ChannelType.REST_API: RestAPIChannelAdapter(),
}


def get_channel_adapter(channel_type: ChannelType) -> BaseChannelAdapter:
    return _ADAPTERS[channel_type]
