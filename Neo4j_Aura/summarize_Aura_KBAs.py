# -*- coding: utf-8 -*-
"""
Created on Fri Apr 25 11:58:51 2022
@author: Rajesh
I've skipped multiple one-liners/short hand stuff on purpose to make the code more readable.
Endpoint for listing all articles: 
    GET /api/v2/help_center{/locale}/articles
For Neo4j Arua:
    GET https://neo4jaura.zendesk.com/api/v2/help_center/en-us/articles/   
"""

import requests
import bs4 as bs # pip install BeautifulSoup4
from os import path,makedirs, listdir
import shutil 
from datetime import timezone as tz
from datetime import date
from datetime import datetime as dt
import pandas as pd #pip install pandas
import time
import warnings
import traceback
warnings.filterwarnings("ignore")
'''
Change summaryFile, keyWordsToMatch and caseInsensitive if requies#
'''

keyWordsToMatch = []
#Whole word matches with leading or lagging space, periods or commas.
#Uncomment teh next line and add desired keywords here. Else you'll be prompted to enter them
#keyWordsToMatch = ['deprecated','Hello','HI','secuRIty','dbms']

#Rename the output file's name if desired. DO NOT INCLUDE THE FILE EXTENSION
summaryFile='kbaSummary'
#The keyword match is case insesitive by default. Change True to False to make the search case sensitive
caseInsensitive = True



### Nothing to change Below ###
### Nothing to change Below ###
### Nothing to change Below ###
if not keyWordsToMatch:
    print('Enter the keywords to search for, one by one, followed by the Enter key.')
    if caseInsensitive:
        print('The keyword match is case insensitive.')
    else:
        print('The keyword match IS CASE SENSITIVE.')
    print('Once you have entered all the keywords,Hit Enter TWICE')
    while True:
        line = input()
        if line:
            keyWordsToMatch.append(line)
        else:
            break


headers = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
}

imgsFolder = 'kbaImages'
if not path.exists(imgsFolder):
        makedirs(imgsFolder)
        
logsDir = 'Logs'
if not path.exists(logsDir):
    makedirs(logsDir)          

def log(txt): 
    logFile = path.join(logsDir,str(date.today())+'_kbaSummarylogs.log')
    logMsg = '\n'+str(dt.now())+'    ' + str(txt)
    with open(logFile,'a') as f:
        f.write(logMsg) 
def printer(*args):
    print(str(dt.now())[:19]," ".join([arg for arg in args])) 


def readKBA(kbaDict):
    try:
        kbaID = kbaDict['id']
        kbaURL = kbaDict['html_url']
        kbaTitle = kbaDict.get('name')
        kbaTitleLength = len(kbaTitle)
        #Too little or too many lables?
        kbaLabels = kbaDict.get('label_names')
        kbaLabelCount = len(kbaLabels)
        kbaLabels = ', '.join([label for label in kbaLabels])
        creationTime = kbaDict['created_at'][:-1].replace('T',' ')
        creationTime = dt.strptime(creationTime, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.utc) #Ensuring this is timezone aware, to allow finding the age later
        updationTime = kbaDict['updated_at'][:-1].replace('T',' ')
        updationTime = dt.strptime(updationTime, '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz.utc) #Ensuring this is timezone aware, to allow finding the age later
        utcNow = dt.now(tz.utc)
        createdAgeInDays = (utcNow-creationTime).days #Days since creation
        updateAgeInDays = (utcNow-updationTime).days #Days since updated
        outdated = kbaDict['outdated'] # Unsure of this field's significance
        voteSum = kbaDict['vote_sum'] # Vote Score. Negative is bad
        voteCount = kbaDict['vote_count'] # Total Votes. If the Vote score less than total votes means negative votes
        negativeVotes = min(voteSum,voteCount - voteSum)
        kbBody = kbaDict.get('body')
        soup = bs.BeautifulSoup(kbBody, "html.parser")
        allImages = soup.findAll('img')
        imgCount = len(allImages)
        failedImages = 0
        externalImages = []
        for img in allImages:
            try:
                suff = 1
                imgUrl = img.get('src')
                if not (('https://aura.support.neo4j.com/' in imgUrl) or ('https://neotechnology.zendesk.com/' in imgUrl)) or ('support.neo4j.com' in imgUrl) :
                    externalImages.append(imgUrl)                
                fileName = img.get('alt')
                if (fileName is None) or ('image width=' in fileName):
                    fileName = imgUrl.split('/')[-1]  
                fileName = fileName.replace(' ','_')                    
                filePath = path.join(imgsFolder,f'{kbaID}_{fileName}')        
                if '.' not in fileName:
                    filePath = filePath+'.png'               
                while path.exists(filePath):
                    extension = filePath.split('.')[-1]
                    filePathPre = filePath.split('.')[0]
                    filePath =f'{filePathPre}_{suff}.{extension}'
                    suff += 1        
                res = requests.get(imgUrl,headers=headers, stream = True)
                if res.status_code == 200:
                    with open(filePath,'wb') as f:
                        #outdated images ?
                        shutil.copyfileobj(res.raw, f)
                    #printer('Image sucessfully Downloaded: ',filePath)
                else:
                    #Broken Images?
                    failedImages +=1
                    msg = f"Failed to read Image {imgUrl} for KBA {kbaID}.Invalid response"
                    printer(msg)
                    log(msg)
            except Exception as e:
                failedImages +=1
                msg = f"Failed to read Image {imgUrl} for KBA {kbaID}. Exception => {e}"
                printer(msg)
                log(msg)
        externalImages = ',\n'.join([url for url in externalImages])
        #Get Plain Text of body and search for desired keyword?        
        texts = soup.findAll(text=True)
        texts = u" ".join(t.strip() for t in texts)
        if caseInsensitive:
            texts = texts.lower()
           
        keyWordMatched = []
        if caseInsensitive:
            for i, keyWord in enumerate(keyWordsToMatch):
                keyWordsToMatch[i] = keyWord.lower()  
        for keyWord in keyWordsToMatch:
            if (f" {keyWord} " in texts) \
                or (f" {keyWord}." in texts) or (f".{keyWord} " in texts) or (f".{keyWord}." in texts) \
                or (f" {keyWord}," in texts) or (f",{keyWord} " in texts) or (f",{keyWord}," in texts): 
                #Could be simplified with regex
                keyWordMatched.append(keyWord)
        keyWordMatched = ", ".join([word for word in keyWordMatched])
        return {'status':True,'kbaID':kbaID, 'kbaURL':kbaURL, 'kbaTitle':kbaTitle, 'kbaTitleLength':kbaTitleLength,
                'kbaLabels':kbaLabels, 'kbaLabelCount':kbaLabelCount, 'createdAgeInDays':createdAgeInDays,
                'updateAgeInDays':updateAgeInDays, 'outdated':outdated, 'voteSum':voteSum, 'voteCount':voteCount,
                'negativeVotes':negativeVotes, 'imgCount':imgCount, 'failedImages':failedImages,'externalImages':externalImages,'keyWordMatched':keyWordMatched, }
    except Exception as e:
        msg = f"Failed to read KBA {kbaDict['id']}. Exception => {e}. {traceback.format_exc()}"
        printer(msg)
        log(msg)
        return {'status':False}

currentpage = 'https://neo4jaura.zendesk.com/api/v2/help_center/en-us/articles/'
oneArticleURL = 'https://neo4jaura.zendesk.com/api/v2/help_center/en-us/articles.json?page=1&per_page=1' 
startedTime = dt.now()
msg = 'Execution Started'
log(msg)
printer(msg)   
msg = 'Started Reading the Artciles.'
log(msg)
printer(msg)
articleCount = requests.get(oneArticleURL).json()['count']
#articlesFetchedCount = 0
msg = f'Total number of Articles -> {articleCount}'
log(msg)
printer(msg)

summaryFile = summaryFile+'.xlsx'    
cols = [ 'kbaID','kbaURL','kbaTitle','kbaTitleLength','createdAgeInDays', 
        'updateAgeInDays', 'outdated','voteSum', 'voteCount',
        'negativeVotes',  'kbaLabels','kbaLabelCount',
        'imgCount','failedImages', 'externalImages','keyWordMatched', 
        ]
kbaSummary = pd.DataFrame(columns=cols) 
failedKBAs = 0
while currentpage is not None:
    getArticles = requests.get(currentpage).json()
    allArticlesDicts = getArticles['articles']
    for article in allArticlesDicts:
        kbaResult = readKBA(article)
        if kbaResult['status']:
            del kbaResult['status']
            kbaSummary = kbaSummary.append(kbaResult,ignore_index=True)
        else:
            failedKBAs +=1
            
    #articlesFetchedCount += len(allArticlesDicts)
    msg = f"Finished Reading page {getArticles.get('page')} of {getArticles.get('page_count')}."
    log(msg)
    printer(msg)        
    currentpage = getArticles.get('next_page',None)   
kbaSummary.to_excel(summaryFile,index=False)    
ended = time.time()    
endedTime = dt.now()
if failedKBAs >0:
    failMsg = f'Failed to read {failedKBAs} articles\n'
else:
    failMsg = ''
msg = f'\nAll Operations completed. Total KBAs processed -> {articleCount}.{failMsg} Output file created -> "{summaryFile}". \n \
    {len(listdir(imgsFolder))}Images downloaded in the "{imgsFolder}" folder. \n \
    Time Taken = {(endedTime-startedTime).seconds} seconds'
log(msg)
printer(msg) 
