import requests
import re
import random
import configparser
from bs4 import BeautifulSoup
from flask import Flask, request, abort
from imgurpython import ImgurClient

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *

app = Flask(__name__)
config = configparser.ConfigParser()
config.read("config.ini")

line_bot_api = LineBotApi(config['line_bot']['Channel_Access_Token'])
handler = WebhookHandler(config['line_bot']['Channel_Secret'])
client_id = config['imgur_api']['Client_ID']
client_secret = config['imgur_api']['Client_Secret']
album_id = config['imgur_api']['Album_ID']
API_Get_Image = config['other_api']['API_Get_Image']


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    # print("body:",body)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'ok'


def pattern_mega(text):
    patterns = [
        'mega', 'mg', 'mu', 'ＭＥＧＡ', 'ＭＥ', 'ＭＵ',
        'ｍｅ', 'ｍｕ', 'ｍｅｇａ', 'GD', 'MG', 'google',
    ]
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True


def eyny_movie():
    target_url = 'http://www.eyny.com/forum-205-1.html'
    print('Start parsing eynyMovie....')
    rs = requests.session()
    res = rs.get(target_url, verify=False)
    soup = BeautifulSoup(res.text, 'html.parser')
    content = ''
    for titleURL in soup.select('.bm_c tbody .xst'):
        if pattern_mega(titleURL.text):
            title = titleURL.text
            if '11379780-1-3' in titleURL['href']:
                continue
            link = 'http://www.eyny.com/' + titleURL['href']
            data = '{}\n{}\n\n'.format(title, link)
            content += data
    return content


def apple_news():
    target_url = 'https://tw.appledaily.com/new/realtime'
    print('Start parsing appleNews....')
    rs = requests.session()
    res = rs.get(target_url, verify=False)
    soup = BeautifulSoup(res.text, 'html.parser')
    content = ""
    for index, data in enumerate(soup.select('.rtddt a'), 0):
        if index == 5:
            return content
        link = data['href']
        content += '{}\n\n'.format(link)
    return content


def get_page_number(content):
    start_index = content.find('index')
    end_index = content.find('.html')
    page_number = content[start_index + 5: end_index]
    return int(page_number) + 1


def craw_page(res, push_rate):
    soup_ = BeautifulSoup(res.text, 'html.parser')
    article_seq = []
    for r_ent in soup_.find_all(class_="r-ent"):
        try:
            # 先得到每篇文章的篇url
            link = r_ent.find('a')['href']
            if link:
                # 確定得到url再去抓 標題 以及 推文數
                title = r_ent.find(class_="title").text.strip()
                rate = r_ent.find(class_="nrec").text
                url = 'https://www.ptt.cc' + link
                if rate:
                    rate = 100 if rate.startswith('爆') else rate
                    rate = -1 * int(rate[1]) if rate.startswith('X') else rate
                else:
                    rate = 0
                # 比對推文數
                if int(rate) >= push_rate:
                    article_seq.append({
                        'title': title,
                        'url': url,
                        'rate': rate,
                    })
        except Exception as e:
            # print('crawPage function error:',r_ent.find(class_="title").text.strip())
            print('本文已被刪除', e)
    return article_seq


def crawl_page_gossiping(res):
    soup = BeautifulSoup(res.text, 'html.parser')
    article_gossiping_seq = []
    for r_ent in soup.find_all(class_="r-ent"):
        try:
            # 先得到每篇文章的篇url
            link = r_ent.find('a')['href']

            if link:
                # 確定得到url再去抓 標題 以及 推文數
                title = r_ent.find(class_="title").text.strip()
                url_link = 'https://www.ptt.cc' + link
                article_gossiping_seq.append({
                    'url_link': url_link,
                    'title': title
                })

        except Exception as e:
            # print u'crawPage function error:',r_ent.find(class_="title").text.strip()
            # print('本文已被刪除')
            print('delete', e)
    return article_gossiping_seq


def ptt_gossiping():
    rs = requests.session()
    load = {
        'from': '/bbs/Gossiping/index.html',
        'yes': 'yes'
    }
    res = rs.post('https://www.ptt.cc/ask/over18', verify=False, data=load)
    soup = BeautifulSoup(res.text, 'html.parser')
    all_page_url = soup.select('.btn.wide')[1]['href']
    start_page = get_page_number(all_page_url)
    index_list = []
    article_gossiping = []
    for page in range(start_page, start_page - 2, -1):
        page_url = 'https://www.ptt.cc/bbs/Gossiping/index{}.html'.format(page)
        index_list.append(page_url)

    # 抓取 文章標題 網址 推文數
    while index_list:
        index = index_list.pop(0)
        res = rs.get(index, verify=False)
        # 如網頁忙線中,則先將網頁加入 index_list 並休息1秒後再連接
        if res.status_code != 200:
            index_list.append(index)
            # print u'error_URL:',index
            # time.sleep(1)
        else:
            article_gossiping = crawl_page_gossiping(res)
            # print u'OK_URL:', index
            # time.sleep(0.05)
    content = ''
    for index, article in enumerate(article_gossiping, 0):
        if index == 15:
            return content
        data = '{}\n{}\n\n'.format(article.get('title', None), article.get('url_link', None))
        content += data
    return content


def ptt_beauty():
    rs = requests.session()
    res = rs.get('https://www.ptt.cc/bbs/Beauty/index.html', verify=False)
    soup = BeautifulSoup(res.text, 'html.parser')
    all_page_url = soup.select('.btn.wide')[1]['href']
    start_page = get_page_number(all_page_url)
    page_term = 2  # crawler count
    push_rate = 10  # 推文
    index_list = []
    article_list = []
    for page in range(start_page, start_page - page_term, -1):
        page_url = 'https://www.ptt.cc/bbs/Beauty/index{}.html'.format(page)
        index_list.append(page_url)

    # 抓取 文章標題 網址 推文數
    while index_list:
        index = index_list.pop(0)
        res = rs.get(index, verify=False)
        # 如網頁忙線中,則先將網頁加入 index_list 並休息1秒後再連接
        if res.status_code != 200:
            index_list.append(index)
            # print u'error_URL:',index
            # time.sleep(1)
        else:
            article_list = craw_page(res, push_rate)
            # print u'OK_URL:', index
            # time.sleep(0.05)
    content = ''
    for article in article_list:
        data = '[{} push] {}\n{}\n\n'.format(article.get('rate', None), article.get('title', None),
                                             article.get('url', None))
        content += data
    return content


def ptt_hot():
    target_url = 'http://disp.cc/b/PttHot'
    print('Start parsing pttHot....')
    rs = requests.session()
    res = rs.get(target_url, verify=False)
    soup = BeautifulSoup(res.text, 'html.parser')
    content = ""
    for data in soup.select('#list div.row2 div span.listTitle'):
        title = data.text
        link = "http://disp.cc/b/" + data.find('a')['href']
        if data.find('a')['href'] == "796-59l9":
            break
        content += '{}\n{}\n\n'.format(title, link)
    return content


def movie():
    target_url = 'http://www.atmovies.com.tw/movie/next/0/'
    print('Start parsing movie ...')
    rs = requests.session()
    res = rs.get(target_url, verify=False)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    content = ""
    for index, data in enumerate(soup.select('ul.filmNextListAll a')):
        if index == 20:
            return content
        title = data.text.replace('\t', '').replace('\r', '')
        link = "http://www.atmovies.com.tw" + data['href']
        content += '{}\n{}\n'.format(title, link)
    return content


def technews():
    target_url = 'https://technews.tw/'
    print('Start parsing movie ...')
    rs = requests.session()
    res = rs.get(target_url, verify=False)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    content = ""

    for index, data in enumerate(soup.select('article div h1.entry-title a')):
        if index == 12:
            return content
        title = data.text
        link = data['href']
        content += '{}\n{}\n\n'.format(title, link)
    return content


def panx():
    target_url = 'https://panx.asia/'
    print('Start parsing ptt hot....')
    rs = requests.session()
    res = rs.get(target_url, verify=False)
    soup = BeautifulSoup(res.text, 'html.parser')
    content = ""
    for data in soup.select('div.container div.row div.desc_wrap h2 a'):
        title = data.text
        link = data['href']
        content += '{}\n{}\n\n'.format(title, link)
    return content


def oil_price():
    target_url = 'https://gas.goodlife.tw/'
    rs = requests.session()
    res = rs.get(target_url, verify=False)
    soup = BeautifulSoup(res.text, 'html.parser')
    title = soup.select('#main')[0].text.replace('\n', '').split('(')[0]
    gas_price = soup.select('#gas-price')[0].text.replace('\n\n\n', '').replace(' ', '')
    cpc = soup.select('#cpc')[0].text.replace(' ', '')
    content = '{}\n{}{}'.format(title, gas_price, cpc)
    return content


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print("event.reply_token:", event.reply_token)
    print("event.message.text:", event.message.text)
    if event.message.text.lower() == "eyny":
        content = eyny_movie()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content))
        return 0
    if event.message.text == "蘋果即時新聞":
        content = apple_news()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content))
        return 0
    if event.message.text == "PTT 表特版 近期大於 10 推的文章":
        content = ptt_beauty()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content))
        return 0
    if event.message.text == "來張 imgur 正妹圖片":
        client = ImgurClient(client_id, client_secret)
        images = client.get_album_images(album_id)
        index = random.randint(0, len(images) - 1)
        url = images[index].link
        image_message = ImageSendMessage(
            original_content_url=url,
            preview_image_url=url
        )
        line_bot_api.reply_message(
            event.reply_token, image_message)
        return 0
    if event.message.text == "隨便來張正妹圖片":
        image = requests.get(API_Get_Image)
        url = image.json().get('Url')
        image_message = ImageSendMessage(
            original_content_url=url,
            preview_image_url=url
        )
        line_bot_api.reply_message(
            event.reply_token, image_message)
        return 0
    if event.message.text == "近期熱門廢文":
        content = ptt_hot()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content))
        return 0
    if event.message.text == "即時廢文":
        content = ptt_gossiping()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content))
        return 0
    if event.message.text == "近期上映電影":
        content = movie()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content))
        return 0
    if event.message.text == "觸電網-youtube":
        target_url = 'https://www.youtube.com/user/truemovie1/videos'
        rs = requests.session()
        res = rs.get(target_url, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        seqs = ['https://www.youtube.com{}'.format(data.find('a')['href']) for data in soup.select('.yt-lockup-title')]
        line_bot_api.reply_message(
            event.reply_token, [
                TextSendMessage(text=seqs[random.randint(0, len(seqs) - 1)]),
                TextSendMessage(text=seqs[random.randint(0, len(seqs) - 1)])
            ])
        return 0
    if event.message.text == "科技新報":
        content = technews()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content))
        return 0
    if event.message.text == "PanX泛科技":
        content = panx()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content))
        return 0
    if event.message.text == "職安訓練":
        buttons_template = TemplateSendMessage(
            alt_text='職安訓練 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='訓練單位評鑑',
                        text='訓練單位評鑑'
                    ),
                    MessageTemplateAction(
                        label='訓練單位認可',
                        text='訓練單位認可'
                    ),
                    MessageTemplateAction(
                        label='訓練單位管理',
                        text='訓練單位管理'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0
    if event.message.text == "訓練單位評鑑":
        buttons_template = TemplateSendMessage(
            alt_text='訓練單位評鑑 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='評鑑法規',
                        text='評鑑法規'
                    ),
                    MessageTemplateAction(
                        label='評鑑作業方式',
                        text='評鑑作業方式'
                    ),
                    MessageTemplateAction(
                        label='評鑑系統操作',
                        text='評鑑系統操作'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0

    if event.message.text == "評鑑法規":
        buttons_template = TemplateSendMessage(
            alt_text='評鑑法規 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
               thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='職衛訓練評鑑要點',
                        text='職業安全衛生教育訓練單位評鑑作業要點如下'
                    )
                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0 

    if event.message.text == "評鑑作業方式":
        carousel_template_message = TemplateSendMessage(
            alt_text='評鑑作業方式 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='說明會',
                                text='說明會'
                            ),
                            MessageTemplateAction(
                                label='公告',
                                text='公告'
                            ),
                            MessageTemplateAction(
                                label='評鑑主動申請',
                                text='評鑑主動申請'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='評鑑自評作業',
                                text='評鑑自評作業'
                            ),
                            MessageTemplateAction(
                                label='實地審查',
                                text='實地審查'
                            ),
                            MessageTemplateAction(
                                label='評鑑公告結果',
                                text='評鑑公告結果'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    )
            
             
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template_message)
        return 0  
    if event.message.text == "說明會":
        buttons_template = TemplateSendMessage(
            alt_text='說明會 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='請問評鑑說明會何時舉辦?',
                        text='年度評鑑說明會會依評鑑年度作業期程公告辦理，請靜候主管機關發函通知及留意訓練資訊網公告'
                    ),
                    MessageTemplateAction(
                        label='評鑑說明會的內容?',
                        text='年度評鑑說明會主要說明以下事項：\n1.年度的評鑑作業期程\n2.申請階段及通過申請後各階段之作業重點\n3.評鑑系統操作說明\n4.其他主管機關指示及評鑑作業事項說明\n相關議程內容請靜候主管機關通知及留意訓練資訊網公告'
                    ),
                    MessageTemplateAction(
                        label='其他',
                        text='其他'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0 
    if event.message.text == "公告":
        buttons_template = TemplateSendMessage(
            alt_text='公告 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='請問評鑑說明會何時舉辦?',
                        text='年度評鑑說明會會依評鑑年度作業期程公告辦理，請靜候主管機關發函通知及留意訓練資訊網公告'
                    ),
                    MessageTemplateAction(
                        label='評鑑申請會以何種方式通知?',
                        text='訓練單位評鑑申請，主管機關會依年度作業期程以公函方式通知職業訓練機構，訓練機構在收到通知後，應於公告截止日前檢附文件提出申請'
                    ),
                    MessageTemplateAction(
                        label='其他',
                        text='其他'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0     
    if event.message.text == "請問評鑑說明會何時舉辦?":
        buttons_template = TemplateSendMessage(
            alt_text='請問評鑑說明會何時舉辦 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
               thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='請問評鑑說明會何時舉辦?',
                        text='年度評鑑說明會會依評鑑年度作業期程公告辦理，請靜候主管機關發函通知及留意訓練資訊網公告'
                    )
                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0 
    if event.message.text == "評鑑主動申請":
        buttons_template = TemplateSendMessage(
            alt_text='評鑑主動申請 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='申請以何種方式通知?',
                        text='訓練單位評鑑申請，主管機關會依年度作業期程以公函方式通知職業訓練機構，訓練機構在收到通知後，應於公告截止日前檢附文件提出申請'
                    ),
                    MessageTemplateAction(
                        label='申請應符合哪一些資格？',
                        text='申請應符合哪一些資格？'
                    ),
                    MessageTemplateAction(
                        label='同時申請管理及技術類評鑑？',
                        text='不行，依現行規定申請時僅能擇一職類提出申請，請於提出申請前審慎評估欲申請評鑑之職類'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0 
    if event.message.text == "評鑑自評作業":
        buttons_template = TemplateSendMessage(
            alt_text='評鑑自評作業 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='自評作業的期程通知方式？',
                        text='單位自評作業依年度評鑑作業期程通知，單位若通過評鑑申請，後續自評作業將以公函方式通知，請靜候主管機關發函通知及留意評鑑系統之公告'
                    ),
                    MessageTemplateAction(
                        label='自評作業文件繳交方式？',
                        text='自評作業文件之繳交，請依主管機關公告通知，於截止日前，發函並檢附相關紙本文件資料予評鑑機構'
                    ),
                    MessageTemplateAction(
                        label='其他',
                        text='其他'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0   
    if event.message.text == "實地審查":
        buttons_template = TemplateSendMessage(
            alt_text='實地審查 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='實地審查的日期及時間安排?',
                        text='評鑑實地審查之日期及時間，請配合評鑑機構之調查進行後續安排，受評單位不得指定評鑑日期'
                    ),
                    MessageTemplateAction(
                        label='技術職類會安排實際課程？',
                        text='技術職類實地訪查部分，受評單位於評鑑當日，應實際開辦受評職類術科實習課程，讓評鑑委員針對術科辦訓狀況進行評核'
                    ),
                    MessageTemplateAction(
                        label='其他',
                        text='其他'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0  
    if event.message.text == "評鑑公告結果":
        buttons_template = TemplateSendMessage(
            alt_text='評鑑公告結果 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
               thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='評鑑結果如何通知?',
                        text='單位完成評鑑後，評鑑機構會議年度評鑑作業期程，主管機關將以公函方式通知受評單位評鑑結果及等第，並將單位之評鑑結果公告於職業安全衛生教育訓練資訓網'
                    )
                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0          
    if event.message.text == "申請應符合哪一些資格？":
        carousel_template_message = TemplateSendMessage(
            alt_text='ImageCarousel template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/jacob'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0 
    if event.message.text == "評鑑系統操作":
        buttons_template = TemplateSendMessage(
            alt_text='評鑑系統操作 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='系統操作主動申請',
                        text='系統操作主動申請'
                    ),
                    MessageTemplateAction(
                        label='系統操作自評作業',
                        text='系統操作自評作業'
                    ),
                    MessageTemplateAction(
                        label='系統操作公告結果',
                        text='系統操作公告結果'
                    )
                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0 
    
    if event.message.text == "系統操作主動申請":
        carousel_template_message = TemplateSendMessage(
            alt_text='系統操作主動申請 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0 
    if event.message.text == "系統操作自評作業":
        carousel_template_message = TemplateSendMessage(
            alt_text='系統操作自評作業 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-1'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0   
    if event.message.text == "系統操作公告結果":
        carousel_template_message = TemplateSendMessage(
            alt_text='系統操作公告結果 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-2'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0         
    if event.message.text == "訓練單位認可":
        buttons_template = TemplateSendMessage(
            alt_text='訓練單位認可 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='認可法規',
                        text='認可法規'
                    ),
                    MessageTemplateAction(
                        label='認可作業方式',
                        text='認可作業方式'
                    ),
                    MessageTemplateAction(
                        label='認可系統操作',
                        text='認可系統操作'
                    )
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0   
    if event.message.text == "認可法規":
        buttons_template = TemplateSendMessage(
            alt_text='認可法規 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
               thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='職衛訓練認可作業要點',
                        text='職業安全衛生教育訓練單位認可作業要點如下'
                    )
                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0      
    if event.message.text == "認可作業方式":
        buttons_template = TemplateSendMessage(
            alt_text='認可作業方式 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='線上申請',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='公告結果',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='年度開班計畫填報',
                        text='暫無回應訊息'
                    )
                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0   
    if event.message.text == "認可系統操作":
        buttons_template = TemplateSendMessage(
            alt_text='認可系統操作 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='系統操作線上申請',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='系統操作年度開班計畫填報',
                        text='暫無回應訊息'
                    )

                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0   
    if event.message.text == "訓練單位管理":
        carousel_template_message = TemplateSendMessage(
            alt_text='訓練單位管理 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='訓練單位管理法規',
                                text='訓練單位管理法規'
                            ),
                            MessageTemplateAction(
                                label='初訓',
                                text='初訓'
                            ),
                            MessageTemplateAction(
                                label='在職',
                                text='在職'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='查班課',
                                text='查班課'
                            ),
                            MessageTemplateAction(
                                label='數據',
                                text='數據'
                            ),
                            MessageTemplateAction(
                                label='輔導員訓練',
                                text='輔導員訓練'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='管理實務研習',
                                text='管理實務研習'
                            ),
                            MessageTemplateAction(
                                label='滿意度問卷',
                                text='滿意度問卷'
                            ),
                            MessageTemplateAction(
                                label='其他',
                                text='其他'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    )
            
             
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template_message)
        return 0  
  
    if event.message.text == "訓練單位管理法規":
        buttons_template = TemplateSendMessage(
            alt_text='訓練單位管理法規 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='證書訓練',
                        text='證書訓練'
                    ),
                    MessageTemplateAction(
                        label='訓練單位',
                        text='訓練單位'
                    ),
                    MessageTemplateAction(
                        label='其他1',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='其他2',
                        text='暫無回應訊息'
                    )
                    

                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0   
    if event.message.text == "證書訓練":
        carousel_template_message = TemplateSendMessage(
            alt_text='證書訓練 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-3'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0   
    if event.message.text == "訓練單位":
        carousel_template_message = TemplateSendMessage(
            alt_text='訓練單位 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-4'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0    
    if event.message.text == "數據":
        carousel_template_message = TemplateSendMessage(
            alt_text='數據 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-5'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0            
    if event.message.text == "初訓":
        buttons_template = TemplateSendMessage(
            alt_text='初訓 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='線上報班',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='線上核班',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='異動申請',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='換補發證書',
                        text='暫無回應訊息'
                    )
                    

                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0     
    if event.message.text == "在職":
        buttons_template = TemplateSendMessage(
            alt_text='在職 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='線上報班',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='線上核班',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='異動申請',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='換補發證書',
                        text='暫無回應訊息'
                    )
                    

                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0    
    if event.message.text == "輔導員訓練":
        buttons_template = TemplateSendMessage(
            alt_text='輔導員訓練 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='公告',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='受理報名',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='通知上課',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='線上列印證書',
                        text='線上列印證書'
                    ),
                    

                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0  
    if event.message.text == "管理實務研習":
        buttons_template = TemplateSendMessage(
            alt_text='管理實務研習 template',
            template=ButtonsTemplate(
                title='選擇服務',
                text='請選擇',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='公告',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='受理報名',
                        text='暫無回應訊息'
                    ),
                    MessageTemplateAction(
                        label='通知上課',
                        text='暫無回應訊息'
                    )

                    

                 
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0    
    if event.message.text == "職安測驗":
        carousel_template_message = TemplateSendMessage(
            alt_text='職安測驗 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試場認可',
                                text='試場認可'
                            ),
                            MessageTemplateAction(
                                label='報考資訊',
                                text='報考資訊'
                            ),
                            MessageTemplateAction(
                                label='成績與證書',
                                text='成績與證書'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試務作業',
                                text='試務作業'
                            ),
                            MessageTemplateAction(
                                label='系統操作',
                                text='系統操作'
                            ),
                            MessageTemplateAction(
                                label='試場管理',
                                text='試場管理'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    )
                  
            
             
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template_message)
        return 0    
    if event.message.text == "試場認可":
        carousel_template_message = TemplateSendMessage(
            alt_text='試場認可 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試場認可法規',
                                text='試場認可法規'
                            ),
                            MessageTemplateAction(
                                label='試場認可相關',
                                text='試場認可相關'
                            ),
                            MessageTemplateAction(
                                label='試場異動',
                                text='試場異動'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='屆期認可',
                                text='屆期認可'
                            ),
                            MessageTemplateAction(
                                label='認可資格審查',
                                text='認可資格審查'
                            ),
                            MessageTemplateAction(
                                label='實地評鑑',
                                text='實地評鑑'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='模擬演練',
                                text='模擬演練'
                            ),
                            MessageTemplateAction(
                                label='資格條件',
                                text='資格條件'
                            ),
                            MessageTemplateAction(
                                label='廢止機制',
                                text='廢止機制'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='場地管理',
                                text='場地管理'
                            ),
                            MessageTemplateAction(
                                label='人員訓練',
                                text='人員訓練'
                            ),
                            MessageTemplateAction(
                                label='其他',
                                text='其他'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    )
                  
            
             
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template_message)
        return 0 
    if event.message.text == "認可資格審查":
        carousel_template_message = TemplateSendMessage(
            alt_text='認可資格審查 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-6'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0       
    if event.message.text == "報考資訊":
        carousel_template_message = TemplateSendMessage(
            alt_text='報考資訊 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='報考資訊法規',
                                text='報考資訊法規'
                            ),
                            MessageTemplateAction(
                                label='測驗方式',
                                text='測驗方式'
                            ),
                            MessageTemplateAction(
                                label='開辦職類',
                                text='開辦職類'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試場名稱、資訊、位置',
                                text='試場名稱、資訊、位置'
                            ),
                            MessageTemplateAction(
                                label='測驗日程、日期',
                                text='測驗日程、日期'
                            ),
                            MessageTemplateAction(
                                label='報名方式',
                                text='報名方式'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試題範圍',
                                text='試題範圍'
                            ),
                            MessageTemplateAction(
                                label='測驗收費',
                                text='測驗收費'
                            ),
                            MessageTemplateAction(
                                label='報考資格',
                                text='報考資格'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='考古題',
                                text='考古題'
                            ),
                            MessageTemplateAction(
                                label='再次報考(補考)',
                                text='再次報考(補考)'
                            ),
                            MessageTemplateAction(
                                label='測驗身分證明文件',
                                text='測驗身分證明文件'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    )
                  
            
             
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template_message)
        return 0   
    if event.message.text == "測驗方式":
        carousel_template_message = TemplateSendMessage(
            alt_text='測驗方式 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-7'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0  
    if event.message.text == "開辦職類":
        carousel_template_message = TemplateSendMessage(
            alt_text='開辦職類 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-8'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0     
    if event.message.text == "試場名稱、資訊、位置":
        carousel_template_message = TemplateSendMessage(
            alt_text='試場名稱、資訊、位置 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-10'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0   
    if event.message.text == "測驗日程、日期":
        carousel_template_message = TemplateSendMessage(
            alt_text='測驗日程、日期 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-11'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0     
    if event.message.text == "測驗收費":
        carousel_template_message = TemplateSendMessage(
            alt_text='測驗收費 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-12'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0    
    if event.message.text == "測驗身分證明文件":
        carousel_template_message = TemplateSendMessage(
            alt_text='測驗收費 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-13'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0                   
    if event.message.text == "成績與證書":
        carousel_template_message = TemplateSendMessage(
            alt_text='成績與證書 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='證書補發(遺失)',
                                text='證書補發(遺失)'
                            ),
                            MessageTemplateAction(
                                label='證書換發(更名)',
                                text='證書換發(更名)'
                            ),
                            MessageTemplateAction(
                                label='證書用途',
                                text='證書用途'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='模擬測驗',
                                text='模擬測驗'
                            ),
                            MessageTemplateAction(
                                label='證書效力',
                                text='證書效力'
                            ),
                            MessageTemplateAction(
                                label='成績及證書查詢',
                                text='成績及證書查詢'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='成績複查',
                                text='成績複查'
                            ),
                            MessageTemplateAction(
                                label='其他1',
                                text='其他1'
                            ),
                            MessageTemplateAction(
                                label='其他2',
                                text='其他2'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    )
                   
                  
            
             
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template_message)
        return 0 
    if event.message.text == "證書補發(遺失)":
        carousel_template_message = TemplateSendMessage(
            alt_text='證書補發(遺失) template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-14'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0   
    if event.message.text == "證書換發(更名)":
        carousel_template_message = TemplateSendMessage(
            alt_text='證書換發(更名) template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-15'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0  
    if event.message.text == "證書效力":
        carousel_template_message = TemplateSendMessage(
            alt_text='證書效力 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-16'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0                     
    if event.message.text == "試務作業":
        carousel_template_message = TemplateSendMessage(
            alt_text='試務作業 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試務作業法規',
                                text='試務作業法規'
                            ),
                            MessageTemplateAction(
                                label='測驗期程',
                                text='測驗期程'
                            ),
                            MessageTemplateAction(
                                label='報名作業',
                                text='報名作業'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='報名人數限制',
                                text='報名人數限制'
                            ),
                            MessageTemplateAction(
                                label='取消報名',
                                text='取消報名'
                            ),
                            MessageTemplateAction(
                                label='姓名為特殊字',
                                text='姓名為特殊字'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='測驗委託',
                                text='測驗委託'
                            ),
                            MessageTemplateAction(
                                label='報名資料審查',
                                text='報名資料審查'
                            ),
                            MessageTemplateAction(
                                label='身心障礙考生延長測驗時間',
                                text='身心障礙考生延長測驗時間'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='退費規範',
                                text='退費規範'
                            ),
                            MessageTemplateAction(
                                label='修改應試者基本資料',
                                text='修改應試者基本資料'
                            ),
                            MessageTemplateAction(
                                label='延後測驗時間',
                                text='延後測驗時間'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='延長報名時間',
                                text='延長報名時間'
                            ),
                            MessageTemplateAction(
                                label='測驗服務費繳費時間',
                                text='測驗服務費繳費時間'
                            ),
                            MessageTemplateAction(
                                label='異動測驗日期',
                                text='異動測驗日期'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='繳費期限',
                                text='繳費期限'
                            ),
                            MessageTemplateAction(
                                label='繳費方式',
                                text='繳費方式'
                            ),
                            MessageTemplateAction(
                                label='繳費收據',
                                text='繳費收據'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='空白證書',
                                text='空白證書'
                            ),
                            MessageTemplateAction(
                                label='作廢證書',
                                text='作廢證書'
                            ),
                            MessageTemplateAction(
                                label='異動測驗期程',
                                text='異動測驗期程'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='場次、座位編排',
                                text='場次、座位編排'
                            ),
                            MessageTemplateAction(
                                label='安排監場人員',
                                text='安排監場人員'
                            ),
                            MessageTemplateAction(
                                label='測驗前檢查作業',
                                text='測驗前檢查作業'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試務用表單',
                                text='試務用表單'
                            ),
                            MessageTemplateAction(
                                label='製作證書',
                                text='製作證書'
                            ),
                            MessageTemplateAction(
                                label='測驗期間偶發事件',
                                text='測驗期間偶發事件'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='統計報表',
                                text='統計報表'
                            ),
                            MessageTemplateAction(
                                label='其他1',
                                text='其他1'
                            ),
                            MessageTemplateAction(
                                label='其他2',
                                text='其他2'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    )
                   
                  
            
             
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template_message)
        return 0 
    if event.message.text == "報名作業":
        carousel_template_message = TemplateSendMessage(
            alt_text='報名作業 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-17'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0      
    if event.message.text == "報名人數限制":
        carousel_template_message = TemplateSendMessage(
            alt_text='報名人數限制 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-18'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0     
    if event.message.text == "測驗委託":
        carousel_template_message = TemplateSendMessage(
            alt_text='測驗委託 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-19'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0  
    if event.message.text == "延長報名時間":
        carousel_template_message = TemplateSendMessage(
            alt_text='延長報名時間 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-20'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0        
    if event.message.text == "繳費收據":
        carousel_template_message = TemplateSendMessage(
            alt_text='繳費收據 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-21'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0    

    if event.message.text == "空白證書":
        carousel_template_message = TemplateSendMessage(
            alt_text='空白證書 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-22'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0  
    if event.message.text == "作廢證書":
        carousel_template_message = TemplateSendMessage(
            alt_text='作廢證書 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-23'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0 
    if event.message.text == "異動測驗期程":
        carousel_template_message = TemplateSendMessage(
            alt_text='異動測驗期程 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-24'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0   
    if event.message.text == "安排監場人員":
        carousel_template_message = TemplateSendMessage(
            alt_text='安排監場人員 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-25'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0  
    if event.message.text == "測驗期間偶發事件":
        carousel_template_message = TemplateSendMessage(
            alt_text='測驗期間偶發事件 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-26'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0                                    
    if event.message.text == "系統操作":
        carousel_template_message = TemplateSendMessage(
            alt_text='系統操作 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='專案管理系統',
                                text='專案管理系統'
                            ),
                            MessageTemplateAction(
                                label='管控及輔助系統',
                                text='管控及輔助系統'
                            ),
                            MessageTemplateAction(
                                label='線上模擬測驗',
                                text='線上模擬測驗'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試務管理系統',
                                text='試務管理系統'
                            ),
                            MessageTemplateAction(
                                label='測驗系統',
                                text='測驗系統'
                            ),
                            MessageTemplateAction(
                                label='題庫管理系統',
                                text='題庫管理系統'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='訓練單位管理系統',
                                text='訓練單位管理系統'
                            ),
                            MessageTemplateAction(
                                label='統計報表',
                                text='統計報表'
                            ),
                            MessageTemplateAction(
                                label='其他',
                                text='其他'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    )
                    
                  
            
             
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template_message)
        return 0  
    if event.message.text == "試務管理系統":
        carousel_template_message = TemplateSendMessage(
            alt_text='試務管理系統 template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/feqEBNf.jpeg',
                        #image_url='https://i.imgur.com/25DT5ps.jpeg',
                        action=URIAction(
                            label='點擊圖片查看回覆',
                            uri='https://jkisangiboy.wixsite.com/website-27'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0      
    if event.message.text == "試場管理":
        carousel_template_message = TemplateSendMessage(
            alt_text='試場管理 template',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試場管理法規',
                                text='試場管理法規'
                            ),
                            MessageTemplateAction(
                                label='工作人員系統權限',
                                text='工作人員系統權限'
                            ),
                            MessageTemplateAction(
                                label='工作人員資格',
                                text='工作人員資格'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='試場效期',
                                text='試場效期'
                            ),
                            MessageTemplateAction(
                                label='工作人員回訓規定',
                                text='工作人員回訓規定'
                            ),
                            MessageTemplateAction(
                                label='試場廢止條件',
                                text='試場廢止條件'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='人員異動',
                                text='人員異動'
                            ),
                            MessageTemplateAction(
                                label='系統帳號申請',
                                text='系統帳號申請'
                            ),
                            MessageTemplateAction(
                                label='講習活動',
                                text='講習活動'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='年終檢討會',
                                text='年終檢討會'
                            ),
                            MessageTemplateAction(
                                label='行政訪視',
                                text='行政訪視'
                            ),
                            MessageTemplateAction(
                                label='系統訪視',
                                text='系統訪視'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                        title='選擇服務',
                        text='請選擇',
                        actions=[
                            #PostbackTemplateAction(
                              #  label='回傳一個訊息',
                             #   data='將這個訊息偷偷回傳給機器人'
                            #),
                            MessageTemplateAction(
                                label='統計數據',
                                text='統計數據'
                            ),
                            MessageTemplateAction(
                                label='其他1',
                                text='其他1'
                            ),
                            MessageTemplateAction(
                                label='其他2',
                                text='其他2'
                            )
                           # URITemplateAction(
                          #      label='進入1的網頁',
                         #       uri='https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Number_1_in_green_rounded_square.svg/200px-Number_1_in_green_rounded_square.svg.png'
                        #    #)
                        ]
                    )
                    
                  
            
             
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, carousel_template_message)
        return 0     
    
    if event.message.text == "圖片格式":
        carousel_template_message = TemplateSendMessage(
            alt_text='ImageCarousel template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/g8zAYMq.jpg',
                        action=URIAction(
                            label='加我好友試玩',
                            uri='https://line.me/R/ti/p/%40gmy1077x'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0    
    if event.message.text == "影片格式":
        video_message = VideoSendMessage(
        original_content_url='https://i.imgur.com/O332Zet.mp4',
        preview_image_url='https://i.imgur.com/KtmMdOF.png'
        )
        line_bot_api.reply_message(
            event.reply_token,
            video_message)
        return 0    
    if event.message.text == "圖片網址格式":
        carousel_template_message = TemplateSendMessage(
            alt_text='ImageCarousel template',
            template=ImageCarouselTemplate(
                columns=[
                    ImageCarouselColumn(
                        image_url='https://i.imgur.com/KtmMdOF.png',
                        action=URIAction(
                            label='點擊觀看影片',
                            uri='https://i.imgur.com/O332Zet.mp4'
                        ),
                    ),
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            carousel_template_message)
        return 0
    if event.message.text == "音訊格式":
        audio_message = AudioSendMessage(
            original_content_url='https://github.com/busundau500/tempdata/blob/main/1.m4a',
            duration=240000
            )
        line_bot_api.reply_message(
            event.reply_token,
            audio_message)
        return 0    
    carousel_template_message = TemplateSendMessage(
        alt_text='目錄 template',
        template=CarouselTemplate(
            columns=[
                CarouselColumn(
                    thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                    title='選擇服務',
                    text='請選擇',
                    actions=[
                        MessageAction(
                            label='職安訓練',
                            text='職安訓練'
                        ),
                         MessageAction(
                            label='職安測驗',
                            text='職安測驗'
                        )
                       # URIAction(
                         #   label='影片介紹 阿肥bot',
                        #    uri='https://youtu.be/1IxtWgWxtlE'
                       # ),
                  
                    ]
                ),
                
            ]
        )
    )

    line_bot_api.reply_message(event.reply_token, carousel_template_message)




@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    print("package_id:", event.message.package_id)
    print("sticker_id:", event.message.sticker_id)
    # ref. https://developers.line.me/media/messaging-api/sticker_list.pdf
    sticker_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 21, 100, 101, 102, 103, 104, 105, 106,
                   107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125,
                   126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 401, 402]
    index_id = random.randint(0, len(sticker_ids) - 1)
    sticker_id = str(sticker_ids[index_id])
    print(index_id)
    sticker_message = StickerSendMessage(
        package_id='1',
        sticker_id=sticker_id
    )
    line_bot_api.reply_message(
        event.reply_token,
        sticker_message)


if __name__ == '__main__':
    app.run()
