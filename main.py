import os
import re
import requests
import time
import json
from xml.etree import ElementTree
import psycopg2
from psycopg2 import sql
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api import VkUpload
from vk_api.utils import get_random_id

DATABASE_URL = os.environ['DATABASE_URL']
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cursor = conn.cursor()
cursor.execute('SELECT * FROM tokens LIMIT 1')
vktoken = cursor.fetchone()[1]
cursor.close()
conn.close()
session = requests.Session()
vk_session = vk_api.VkApi(token=vktoken)
longpoll = VkLongPoll(vk_session)
vk = vk_session.get_api()

def getquestion(event,qtype='1', date = '2012-01-01',thematic = ''):
    url = 'https://db.chgk.info/xml/random/from_'+date+'/types'+qtype+'/limit1/'+thematic
    questionxml = requests.get(url)
    questionxml = ElementTree.fromstring(questionxml.content)
    question = questionxml.find('./question/Question').text.replace('\n',' ')
    answer = questionxml.find('./question/Answer').text.replace('\n',' ')
    comment = questionxml.find('./question/Comments').text
    if comment != None:
        comment = comment.replace('\n',' ')
    author = questionxml.find('./question/Authors').text
    if author != None:
        author = author.replace('\n',' ')
    passcr = questionxml.find('./question/PassCriteria').text
    if passcr != None:
        passcr = passcr.replace('\n',' ')
    resource = questionxml.find('./question/Sources').text
    if resource != None:
        resource = resource.replace('\n',' ')
    tour = questionxml.find('./question/tournamentTitle').text
    if tour != None:
        tour = tour.replace('\n',' ')
    pic = None
    commentpic = None
    if re.search('\(pic: ',question) != None:
        question = re.split('\)',question, maxsplit = 1)
        pic = re.search('\d\d\d\d\d\d\d\d.jpg',question[0]).group(0)
        pic = 'https://db.chgk.info/images/db/' + pic
        question = question[1]
    if comment != None:
        if re.search('\(pic: ',comment) != None:
            comment = re.split('\)',comment, maxsplit = 1)
            commentpic = re.search('\d\d\d\d\d\d\d\d.jpg',comment[0]).group(0)
            commentpic = 'https://db.chgk.info/images/db/'+pic
            comment = comment[1]
    currtime = int(time.time())
    if event.from_chat:
        ischat = True
        tabid = event.chat_id
    elif event.from_user:
        ischat = False
        tabid = event.user_id
    answered = False
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    values = (ischat, tabid, question, pic, answer, passcr, author, comment, commentpic, resource, tour, currtime, answered, question, pic, answer, passcr, author, comment, commentpic, resource, tour, currtime, answered)
    insert = ('INSERT INTO questions (ischat, tabid, question, pic, answer, pass, author, qcomments, commentpic, sources, tour, created, answered) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (ischat, tabid) DO UPDATE SET question = %s, pic = %s, answer = %s, pass = %s, author = %s, qcomments = %s, commentpic = %s, sources = %s, tour = %s, created = %s, answered = %s')
    cursor.execute(insert, values)
    conn.commit()
    cursor.close()
    conn.close()
    return question,pic

def sendmessage(event,text,pic=None):
    if pic != None:
        upload = VkUpload(vk_session)
        image_url = pic
        image = session.get(image_url, stream=True)
        photo = upload.photo_messages(photos=image.raw)[0]
        attach='photo{}_{}'.format(photo['owner_id'], photo['id'])
        if event.from_user:
            vk.messages.send(
                user_id=event.user_id,
                random_id=get_random_id(),
                attachment=attach,
                message=text
                )
        elif event.from_chat:
            vk.messages.send(
                chat_id=event.chat_id,
                random_id=get_random_id(),
                attachment=attach,
                message=text
                )
    else:
        if event.from_user:
            vk.messages.send(
                user_id=event.user_id,
                random_id=get_random_id(),
                message=text
                )
        elif event.from_chat:
            vk.messages.send(
                chat_id=event.chat_id,
                random_id=get_random_id(),
                message=text
                )


for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
        if event.text == 'Вопрос' or event.text == 'вопрос':
            question, pic = getquestion(event)
            sendmessage(event,question,pic)
