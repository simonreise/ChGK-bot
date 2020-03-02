import re
import requests
import json
from xml.etree import ElementTree
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api import VkUpload

session = requests.Session()
vk_session = vk_api.VkApi(token='5faee013592f2171918b1ea14b101bd2d5312e73cefd211236a775c3274c091153fe20706ca3953669a85')
longpoll = VkLongPoll(vk_session)
vk = vk_session.get_api()

def question(qtype='1', date = '2012-01-01',thematic = ''):
    url = 'https://db.chgk.info/xml/random/from_'+date+'/types'+qtype+'/limit1/'+thematic
    questionxml = requests.get(url)
    questionxml = ElementTree.fromstring(questionxml.content)
    question = questionxml.find('./question/Question').text.replace('\n',' ')
    answer = questionxml.find('./question/Answer').text.replace('\n',' ')
    comment = questionxml.find('./question/Comments').text.replace('\n',' ')
    author = questionxml.find('./question/Authors').text.replace('\n',' ')
    pic = None
    commentpic = None
    if re.search('\(pic: ',question) != None:
        question = re.split(')',question, maxsplit = 1)
        pic = re.search('\d\d\d\d\d\d\d\d.jpg',question[0])
        pic = 'https://db.chgk.info/images/db/' + pic
        question = question[1]
    if re.search('(\pic: ',comment) != None:
        comment = re.split(')',comment, maxsplit = 1)
        commentpic = re.search('\d\d\d\d\d\d\d\d.jpg',comment[0])
        commentpic = 'https://db.chgk.info/images/db/'+pic
        comment = comment[1]
    return question, answer, comment,author,pic,commentpic

def message(text,pic,event):
    if pic != None:
        upload = VkUpload(vk_session)
        image_url = pic
        image = session.get(image_url, stream=True)
        photo = upload.photo_messages(photos=image.raw)[0]
        attach='photo{}_{}'.format(photo['owner_id'], photo['id'])
        if event.from_user:
            vk.messages.send(
                user_id=event.user_id,
                attachment=attach,
                message=text
                )
        elif event.from_chat:
            vk.messages.send(
                chat_id=event.chat_id,
                attachment=attach,
                message=text
                )
    else:
        if event.from_user:
            vk.messages.send(
                user_id=event.user_id,
                message=text
                )
        elif event.from_chat:
            vk.messages.send(
                chat_id=event.chat_id,
                message=text
                )


for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
        if event.text == 'Вопрос' or event.text == 'вопрос':
            question, answer, comment, author, pic, commentpic = question()
            message(question,pic,event)
