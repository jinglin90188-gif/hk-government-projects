"""Explainable business-scope rules, not scores or assertions of eligibility.

Raw records are retained for audit. Only explicit matches enter the default
opportunity list; unclear titles go to review instead of being silently lost.
"""
import re
from collections import Counter

VERSION='2026-10-26-v1'
REFERENCE_URLS=['https://www.smartcitysz.com/home/about',
    'https://gzw.sz.gov.cn/szgq/content/post_9395742.html',
    'https://console.szaicpp.com/cpnportal/home']
RULES=[
 ('交通、口岸及城市感知补充',r'智慧绿色集体运输|交通流量|泊车调查|私家车.*(?:分析|检测).*系统|指挥及控制系统|水质监测系统|航行监察|\b(?:IT|AV)\b.*(?:配线|布线|cabling)|虚拟实境|扩增实境|数码支付|电子钱包'),
 ('通信与基础软件补充',r'网路交换器|网络交换器|流动电话服务|建筑信息模拟|电脑.*(?:硬件|设备)|电脑网络|通讯系统|通信系统|防恶意软件|反恶意软件|通用计算|超融合|网络储存|伺服器'),
 ('算力、云及数据中心',r'算力|智算|超算|数据中心|数据中心|云平台|云服务|云计算|私有云|混合云|虚拟化|伺服器|服务器|储存系统|存储系统|备份系统|\b(?:GPU|HPC|servers?|cloud|data cent(?:re|er)s?|storage|virtuali[sz]ation|backup)\b'),
 ('软件、平台及数字政府',r'信息系统|资讯系统|应用系统|电脑系统|计算机系统|软件|数码政府|数字政府|电子政务|业务平台|管理平台|城市大脑|电子档案|电子文件|数据库|客户关系管理|网络应用|网站|移动应用|流动应用|\b(?:software|information systems?|computer systems?|applications? development|database|CRM|ERP|websites?|web portals?|mobile apps?)\b'),
 ('智慧交通及口岸系统',r'交通管制|交通监察|交通监控|交通信号|交通灯|交通管理.*(?:系统|平台|研究)|交通数据|智能交通|智慧交通|停车.*(?:系统|平台)|泊车.*(?:系统|平台)|出租车.*(?:信息|资讯|系统)|的士.*系统|易通行|自动清关|车辆.*(?:检测|分析|识别).*系统|\b(?:HKeToll|AVCSS|TCSS|ITS)\b|traffic (?:control|surveillance|signal|management|data)|toll (?:collection|system)|vehicle.*(?:inspection|recognition|clearance).*system'),
 ('视频、安防及物联感知',r'闭路电视|CCTV|视频分析|影像分析|视频监控|智能巡查|智能巡检|遥距监控|物联网|物联感知|传感器网络|感测器网络|门禁系统|保安系统|\b(?:IoT|ANPR|RFID|video analytics|video surveillance|access control|security systems?)\b'),
 ('GIS、数字孪生及工程数字化',r'\b(?:GIS|BIM|CIM|LCDM)\b|地理信息|地理资讯|空间数据|空间资讯|三维.*(?:地图|城市|模型)|数字孪生|数码分身|数字分身|智慧工地|智能工地|工程.*(?:数据平台|信息平台)|digital twin|geographic information|geospatial'),
 ('人工智能及数据治理',r'人工智能|人工智慧|机器学习|大模型|数据治理|数据中台|数据平台|数据分析|数据整合|数据集成|大数据|\b(?:AI|artificial intelligence|machine learning|data analytics|data governance|data platform|big data)\b'),
 ('无人车、无人机及机器人',r'无人车|无人驾驶|自动驾驶|无人机|无人飞行|低空|机器人|机械人|飞行.*(?:管理|监管|调度).*系统|\b(?:UAV|UTM|drones?|robotics?|autonomous vehicles?|automated driving)\b'),
 ('网络、通信及网络安全',r'通信网络|通讯网络|无线电|无线网络|无线传输|网络交换机|网络设备|网络安全|资讯安全|信息安全|防火墙|网络基础设施|\b(?:network switches|network equipment|network infrastructure|wireless|radio communication|cybersecurity|cyber security|firewalls?|telecommunication)\b'),
 ('能源及市政数字化',r'能源管理系统|能源管理平台|智慧能源|智能电网|充电.*(?:平台|系统|网络)|充储放|虚拟电厂|电力.*(?:数据|调度|监控).*平台|水务.*(?:数据|监控).*系统|smart grid|energy management system|virtual power plant|charging.*(?:platform|management system)'),
]
EXCLUSIONS=[
 ('一般服务及传统机电工程',r'物业管理|设施管理服务|保安服务|保安及大厦管理|护卫员|洁净|清粪|吸污|膳食|快餐业务|食肆|文创商店|图书馆资料整理|帐篷|宣传服务|活动助理|就业发展|疫苗|胰高血糖素|电脑断层扫描仪|扫描电子显微镜|(?:供应|租赁).*(?:巴士|房车|客货车|货车|电单车|救护车|图书馆车|污水车|水车)|(?:升降机|自动梯|载货电梯|冷水机组|空调装置|泛光灯装置|池水处理装置).*(?:维修|保养|更换)|(?:维修|保养|更换).*(?:升降机|自动梯|空调装置|消防系统)|地盘平整|地基及准备|桩柱地基|游乐设施|有盖行人通道|行人路建上盖|海堤维修|化验|质谱仪|硫酸铝|熟石灰|活性碳|航空法律责任保险|Lift Installations|Lighting at Various|Tunnel Ventilation|District Cooling'),
 ('清洁、保安人手及后勤',r'清洁服务|清洁工|保安员|保安护卫服务|餐饮|膳食|制服|文具|家具|园艺|cleaning services|cleansing services|security guards?|catering|uniforms|stationery|furniture|gardening'),
 ('医药及专用临床设备',r'药品|药物|医疗耗材|内视镜|内窥镜|病床|手术台|检查椅|心电图|超声波诊断|pharmaceutical|medicines?|endoscop|hospital beds?|surgical instruments'),
 ('普通物资及非数字化工程',r'燃料|汽油|柴油|食材|食品|道路重铺|斜坡维修|土方工程|油漆|印刷服务|fuel supply|diesel|food supply|road resurfacing|slope maintenance|printing services'),
]

def classify(row):
    # Never match URLs, department names or generic words like "system" alone.
    title=' '.join(str(row.get(k,'') or '') for k in ['title','title_zh'])
    hits=[(name,m.group(0)) for name,pattern in RULES if (m:=re.search(pattern,title,re.I))]
    exclusions=[name for name,pattern in EXCLUSIONS if re.search(pattern,title,re.I)]
    if hits and exclusions:
        decision='review';reason='同时涉及数字化内容与通常排除的采购，需核对实际范围'
    elif hits:
        decision='include';reason='采购标题明确涉及'+ '、'.join(name for name,_ in hits)
    elif exclusions:
        decision='exclude';reason='采购内容属于'+ '、'.join(exclusions)+'，未见相关数字化范围'
    else:
        decision='review';reason='标题不足以确认业务范围，需阅读项目文件；不是判定为无关'
    return dict(decision=decision,categories=[name for name,_ in hits],
        evidence=[word for _,word in hits],reason=reason,rule_version=VERSION,
        eligibility='仅判断业务相关性；资质、原厂授权及业绩要求须另查招标文件')

def annotate(data):
    for row in data['projects']:row['company_fit']=classify(row)
    counts=Counter(r['company_fit']['decision'] for r in data['projects'])
    data['company_scope']={'rule_version':VERSION,'scoring_enabled':False,
        'counts':dict(counts),'reference_urls':REFERENCE_URLS,
        'note':'参考深智城公开业务版图及用户描述设置业务边界，不代表本公司具备集团全部业绩或投标资格；原始资料保留以便复核。'}
    return data
