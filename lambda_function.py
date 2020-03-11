import json
import boto3
import datetime
import urllib3
import os

def lambda_handler(event, context):
    
    r={}
    
    iamClient = boto3.client('iam')
    users=iamClient.list_users()['Users']
    for user in users:
        r["root"+"/"+user["UserName"]]=checkUser(iamClient, user)
    
    orgClient = boto3.client('organizations')
    accounts = orgClient.list_accounts()['Accounts']    
    i=1
    while i<len(accounts):
        acct=accounts[i];i=i+1
        if isInt(acct["Name"])==True: continue
        r = {**r, **checkAccount(acct)}
    
    reportToSlack(r)
    return

def isInt(s):
    try:
        int (s)
        return True
    except:
        return False

def checkAccount(acct):
    r={}
    sts_client = boto3.client('sts')
    assumed_role_object=sts_client.assume_role(RoleArn="arn:aws:iam::"+acct["Id"]+":role/"+acct["Name"],RoleSessionName=acct["Name"]+"@"+acct["Id"])        
    credentials=assumed_role_object['Credentials']
    iamClient=boto3.client('iam',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],aws_session_token=credentials['SessionToken'])
    users=iamClient.list_users()['Users']
    
    for user in users:
        r[acct["Name"]+"/"+user["UserName"]]=checkUser(iamClient, user)
    
    return r

def checkUser(iamClient, user):
    r={}
    res=iamClient.list_access_keys(UserName=user["UserName"])
    keys=res["AccessKeyMetadata"]
    for key in keys:
        age = datetime.datetime.now(datetime.timezone.utc) - key["CreateDate"]
        if age > datetime.timedelta(days=int(os.getenv("max_allowed_days"))):
            r[key["AccessKeyId"]] = str(age.days) + " days old"
    return r        
    
def reportToSlack(msg):
    http = urllib3.PoolManager()
    r = http.request(
        'POST', os.getenv("slack_hook"), headers={'Content-Type': 'application/json'}, 
        body=json.dumps({
            "username":"iamKeyWatcher",
            "text": "###cronjob-iamKeyWatcher###\nexecution @ (UTC) "+ str(datetime.datetime.now(datetime.timezone.utc)),
            'icon_emoji': ':hamburger:',
            })
        )    
    r = http.request(
        'POST', os.getenv("slack_hook"), headers={'Content-Type': 'application/json'}, 
        body=json.dumps({
            "username":"iamKeyWatcher",
            "text": "done -- all good",
            "blocks": mapToSlackBlocks(msg),
            'icon_emoji': ':hamburger:',
            })
        )
        
    return

def mapToSlackBlocks(map):
    
    # block={"type": "section","text": {"type": "mrkdwn","text": "A message *with some bold text* and _some italicized text_."}}
    blocks=[]
    for k in map:
        if bool(map[k]):
            # block={"type": "section","text": {"type": "mrkdwn","text": "`"+k+"` containers expired keys:\n"+json.dumps(map[k])}}
            block={"type": "section","text": {"type": "mrkdwn","text": "`"+k+"` containers expired keys:\n"+beautifyStrForKeyMap(map[k])}}
            blocks.append(block)
    return blocks

def beautifyStrForKeyMap(map):
    s=""
    for k in map:
        s=s + "key *"+k + "* is " + str(map[k]) + "\n"
    return s

    # TODO implement
    # return {
    #     'statusCode': 200,
    #     'body': json.dumps('Hello from Lambda!')
    # }
