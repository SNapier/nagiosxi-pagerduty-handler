import requests, sys, argparse, os, logging, json, time, yaml
from time import sleep
from logging.handlers import RotatingFileHandler

#NAME
appName = "nagiosxi-pagerduty-handler.py"
#VERSION
appVersion = "0.1.0"

#PATHS
#DEPENDING ON WHERE YOU WANT TO PUT THE REPORTS
appPath = os.path.dirname(os.path.realpath(__file__))

#PUT THE LOG IN SAME DIR BY DEFAULT
log_dir = appPath+"\\"

#LOGGING
## CREATE LOGGER
logger = logging.getLogger(appName)
## DEFAULT LOG LEVEL
logger.setLevel(logging.INFO)

## CREATE CONSOLE LOG HANDLER
ch = logging.StreamHandler()
## CONSOLE HANDLER LOG LEVEL
ch.setLevel(logging.INFO)

#FILE HANDLER
fh = logging.handlers.RotatingFileHandler(log_dir+appName+".log", mode='a', maxBytes=4096, backupCount=0, encoding=None, delay=False)
##FILE LOG LEVEL
fh.setLevel(logging.INFO)

##LOG HANDLER FORMATTING
stdFormat = logging.Formatter('[%(asctime)s] level="%(levelname)s"; name="%(name)s"; message="%(message)s";', datefmt='%Y-%m-%dT%H:%M:%S')
debugFormat = logging.Formatter('[%(asctime)s] level="%(levelname)s"; name="%(name)s"; function="%(funappName)s"; line="%(lineno)d"; message="%(message)s";', datefmt='%Y-%m-%dT%H:%M:%S')

##APPLY LOG HANDLER FORMATTING
ch.setFormatter(stdFormat)
fh.setFormatter(stdFormat)

##ADD LOG HANDLERS
logger.addHandler(ch)
logger.addHandler(fh)

#TIME TO SLEEP BETWEEN RETRY ATTEMPTS
sleepDuration = 5

##NAGIOSXI-PAGERDUTY-HANDLER.YAML
##APIKEY
##ROUTINGKEY
##PAGERDUTY URL
def nagiosxiConfig():
    with open(appPath+"\\nagiosxi-pagerduty-handler.yaml", "r") as yamlfile:
        try:
            data = yaml.load(yamlfile, Loader=yaml.FullLoader)
            r = {"url":data[0]["pgrduty"]["url"],"apikey":data[0]["pgrduty"]["apikey"],"routekey":data[0]["pgrduty"]["routingkey"]}
        except Exception as e:
            logger.error("%s",e)
            r = False
        finally:
            return r

#DEFINE JUSDGEMENT CALL HELPER
#------------------------------
#IS THIS A HARD STATE
def isHardState(meta):
    hardStates = ['hard','HARD']
    if meta.servicestatetype in hardStates:
        return True
    else:
        return False

#HOSTNAME IS NOT BLANK
def hasHostname(meta):
    if meta.hostname != "":
        return True
    else:
        return False

#COMPARE ORIGIN HOSTNAME TO A LIST OF HOSTNAMES TO EXCLUDE FROM FORWARDING EVENTS
def isBanList(meta):
    bannedHosts = ['localhost','LOCALHOST','hostname','HOSTNAME']
    if meta.hostname in bannedHosts:
        return True
    else:
        return False 

#IS THIS SERVICE IN SCHEDULED DOWNTIME
def isInDowntime(meta):
    if int(meta.servicedowntime) > 0:
        return True
    else:
        return False

#--------------------------
#END JUDGEMENT CALL HELPER

#PASS JUDGEMENT
def makeJudgementCall(meta):
    #JUDGEMENT CALLS
    #IN ORDER TO REDUCE ALERT FATIGUE WE CAN MAKE SOME PROGRAMATIC DECISIONS TO
    #PRE-FILTER OUR EVENTS FOR ACTIONABILITY. USING AN EXTERNAL FUNCTION FOR EACH
    #JUDGEMENT PROVIDES FOR EASY ADDITION/REMOVAL OF LOGICS   
    
    #JUDGEMENT CALL: IS THERE A HOSTNAME? (SHOULD BE HANDLED ARG INPUT, WE TRUS BUT VERUFY THAT)
    hashostname = hasHostname(meta)
    if hashostname:
        #JUDGEMENT CALL: IS HOSTNAME IN A BAN LIST?
        isbanned = isBanList(meta)
        if isbanned:
            #FAILED IS BANNED JUDGEMENT CALL
            logger.info("DISCARDED EVENT %s IS IN THE BANNED LIST",meta.hostname)
            sys.exit(2)
        else:
            #JUDGEMENT CALL: IS THERE SCHEDULED DOWNTIME?
            isindowntime = isInDowntime(meta)
            if isindowntime:
                #FAILED IN DOWNTIME JUDGEMENT CALL
                logger.info("DISCARDED EVENT %s IS IN DOWNTIME",meta.servicename)
                sys.exit(2)
            else:
                #JUDGEMENT CALL: IS THIS A HARD STATE?
                ishardstate = isHardState(meta)
                if ishardstate:
                    #PASSED JUDGEMENT CALLS
                    logger.info("DISCARDED SOFT STATE EVENT")
                    isvalid = True
                else:
                    #FAILED HARD STATE JUDGEMENT CALL
                    #LOG AND EXIT
                    logger.critical("HANDLER FAILED TO PROCESS EVENT JUDGEMENT CALLS")
                    sys.exit(2)
                    
    else:
        #FAILED HAS HOSTNAME JUDGEMEMT CALL
        #LOG AND EXIT
        logger.critical("HOSTNAME IS NOT PRESENT IN THE EVENT JUDGEMENT")
        sys.exit(2)
    
    #RETURN JUDGEMENT
    return isvalid

#EVENT SWITCHER
def pdEventType(meta):
    #NOTIFICATION TYPE JUDGEMENT BASED ON PRESIOUS STATE AND CURRENT STATE
    
    #FORMAT SERVICESTATEID:LASTSERVICESTATEID
    i = meta.servicestateid+":"+meta.lastservicestateid
    
    #RETURN EVENT YPE BASED ON THE CURRENTSTATEID AND LASTSERVICESTATEID
    switcher = {
        #WE ARE NOW IN AN OK STATE, TYPE = VARIOUS
        "0:1": "resolve",
        "0:2": "resolve",
        "0:3": "resolve",
        #OK->OK IS EITHER A DUPE OR INJECTED WILL RETURN A DISCARD
        "0:0": "discard",
        #WE ARE NOW IN A WARNING STATE, TYPE = VARIOUS
        "1:0": "trigger",
        "1:2": "trigger",
        "1:3": "trigger",
        #WARNING->WARNING IS A DUPE IN THIS INSTANCE WE WILL DISCARD
        "1:1": "discard",
        #WE ARE NOW IN A CRITICAL STATE, TYPE = VARIOUS
        "2:0": "trigger",
        "2:1": "update",
        "2:3": "update",
        #CRITICAL->CRITICAL IS A DUPE IN THIS INSTANCE WE WILL UPDATE
        "2:2": "update",
        #WE ARE NOW IN AN UNKNOWN STATE
        "3:0": "trigger",
        "3:1": "update",
        "3:2": "update",
        #UNKNOWN->UNKNOWN IS A DUPE WE WILL RETURN DISCARD
        "3:3": "discard"
    }
    
    #DEBUG OUT
    if meta.debug:
        logger.debug("pid["+str(os.getpid())+"] stateTypes["+i+"] eventType["+i+"]")
    
    #RETURN ACTION TYPE
    return switcher.get(i, "failed to get event type")

#PAGERDUTY DEDUP KEY
def getDedupeKey(i, meta):

    #RETURN PROBLEMID OR LAST PROBLEMID BASED ON EVENT TYPE
    switcher = {
        "trigger": meta.serviceproblemid ,
        "update": meta.serviceproblemid ,
        "resolve": meta.lastserviceproblemid
    }
    
    #DEBUG OUT
    if meta.debug:
        logger.debug("pid["+str(os.getpid())+"] eventType["+i+"] dedupKey["+str(switcher.get(i))+"]")
    
    #RETURN DEDUP KEY
    return switcher.get(i)

#PAGERDUTY PAYLOAD
def payloadManifest(etype,dedupe_key,meta):
    config = nagiosxiConfig()
    manifest = {
        "payload": {
            "summary": meta.summary,
            "timestamp": None,
            "source": meta.source,
            "severity": meta.severity,
            "component": meta.component,
            "group": meta.group,
            "class": meta.mclass,
            "custom_details": {
                "serviceout": meta.customdetails
            }
        },
        "routing_key": config['routekey'],
        "dedup_key": dedupe_key,
        "links": [
                    {
                        "href": "https://example.com/",
                        "text": "Link text"
                    }
                ],
        "event_action": etype,
        "client": meta.hostname+"-"+meta.source,
        "client_url": "https://nagiosxi.example.com"
    }

    #SERIALIZE THE MANIFEST DICT
    payload = json.dumps(manifest)
    
    #DEBUG OUT
    if meta.debug:
        logger.debug("pid["+str(os.getpid())+"] eventType["+etype+"] payload["+payload+"]")

    return payload

#SEND PAGERDUTY EVENT
def sendPagerDutyEvent(meta, payload):
    
    #API KEY FROM CONFIGS
    config = nagiosxiConfig()

    #OUR POST AS A SESSION WITH THE TOKEN IN THE HEADER
    pd_session = requests.Session()

    #PAGERDUTY API VERSION 2 REQUIRED HEADERS
    pd_session.headers.update({
        'Authorization': 'Token token='+config['apikey'],
        'Accept': 'application/vnd.pagerduty.com/v2/enqueue'
    })

    #PAGERDUTY API VERSION 2 ENQUEUE URL
    #apiEndpoint = "https://events.pagerduty.com/v2/enqueue"

    #POST INCIDENT
    r = requests.post(url=config['url'],data=payload)

    #PAGER DUTY WILL RETURN A RESPONSE CODE
    # 202 = EVENT PROCESSED
    # 400 = Invalid event format (i.e. JSON parse error) or incorrect event structure
    # 429 = Rate limit reached (too many Events API requests)
    # 5XX = An error occurred on a request.
    # 
    # WE WILL NEED TO DEAL WITH THE API REQUEST LIMIT WITH A RETRY LOOP
    # WHERE THE RETRY COUNT/TIMEOUT CAN BE PASSED VIA NAGIOS MACROS
    #
    attempt = 1
    
    #FIRST TRY FAILED
    if r.status_code in ['400','429']:
        
        #THROW WARNING FAILED FOR FIRST ATEMPT
        logger.warning("pid["+str(os.getpid())+"] eventType["+etype+"] payload["+payload+"] sendEventAttempt["+str(attempt)+"] statusCode["+str(r.status_code)+"] Sleeping for "+str(sleepDuration)+" before retrying.")
        
        #SLEEP FOR X SEXONDS BEFORE RETRYING SENDING EVENT TO PAGER DUTY
        sleep(sleepDuration)

        #INCREMENT ATTEMPT
        attempt += 1
        
        #SEND TO PAGERDUTY AGAIN
        r2 = requests.post(url=config['url'], params=payload)

        #SECOND ATTEMPT AT SEND EVENT
        if r2.statsu_code != 202:
            if meta.debug:
                print(appName+"-DEBUG: pid["+str(os.getpid())+"] eventType["+etype+"] statusCode["+str(r.status_code)+"] sendEventAttempt["+str(attempt)+"] Failed with status code "+str(r2.status_code))    
            #FAILED WE EXIT
            print(appName+"-ERROR: pid["+str(os.getpid())+"] eventType["+etype+"] statusCode["+str(r.status_code)+"] sendEventAttempt["+str(attempt)+"] Failed with status code "+str(r2.status_code))
            sys.exit()
        else:
            if meta.debug:
                print(appName+"-DEBUG: pid["+str(os.getpid())+"] eventType["+etype+"] statusCode["+str(r.status_code)+"] sendEventAttempt["+str(attempt)+"] Successfuly sent event to pager duty")
            
            #SECOND ATTEMPT SUCCESSFUL
            result = r2

    #FIRST TRY WAS SUCCESSFUL        
    elif r.status_code == 202:
        logger.info("pid["+str(os.getpid())+"] eventType["+etype+"] statusCode["+str(r.status_code)+"] sendEventAttempt["+str(attempt)+"] Successfuly sent event to pager duty")
        #FIRST SEND SUCESSFUL WE RETRUN RESULT
        result = r
    else:
        #FAILED WE EXIT
        logger.error("pid["+str(os.getpid())+"] eventType["+etype+"] statusCode["+str(r.status_code)+"] sendEventAttempt["+str(attempt)+"] Failed with message "+str(r.text))
        sys.exit()
    
    #WE HAVE A SUCCESSFUL EVENT OR WE WOULD HAVE EXITIED
    return result

#SEND EVENT TO PAGERDUTY
def handleEvent(etype, meta):
    #RETURN TRUE/FALSE
    if etype == "resolve":
        
        #USING THE SERVICE RPOBLEMID AS THE DEDUP KEY ALLOWS US TO EASILY IDENTIFY
        #AND RETURN THE NEEDED UNIQUE VALUE REQUIRES
        dedupe_key = getDedupeKey(etype,meta)
        
        #PAYLOAD OF PDUTY
        payload = payloadManifest(etype, dedupe_key, meta)
                
        #SEND API REQUEST
        result = sendPagerDutyEvent(meta, payload)

    elif etype == "trigger":
        #USING THE SERVICE RPOBLEMID AS THE DEDUP KEY ALLOWS US TO EASILY IDENTIFY
        #AND RETURN THE NEEDED UNIQUE VALUE REQUIRES
        dedupe_key = getDedupeKey(etype, meta)

        #PAYLOAD OF PDUTY
        payload = payloadManifest(etype, dedupe_key, meta)
        
        #SEND API REQUEST
        result = sendPagerDutyEvent(meta, payload)

    elif etype == "update":
        #USING THE SERVICE RPOBLEMID AS THE DEDUP KEY ALLOWS US TO EASILY IDENTIFY
        #AND RETURN THE NEEDED UNIQUE VALUE REQUIRES
        dedupe_key = getDedupeKey(etype, meta)
        
        #PAYLOAD OF PDUTY EVENT
        payload = payloadManifest(etype, dedupe_key, meta)
        
        #SEND API REQUEST
        result = sendPagerDutyEvent(meta, payload)
        
    elif etype == "discard":
        #WE WERE GIVEN AN UNKNOWN EVENT TYPE WE EXIT
        logger.info("pid["+str(os.getpid())+"] Event was discarded, eventType["+etype+"]")
        sys.exit()

    else:
        #WE WERE GIVEN AN UNKNOWN EVENT TYPE WE EXIT
        logger.error("pid["+str(os.getpid())+"] Failed to handle returned eventType. eventType["+etype+"] is unknown.")
        sys.exit()

    #DEBUG OUT
    if meta.debug:
        logger.debug(appName+"-DEBUG: pid["+str(os.getpid())+"] eventType["+etype+"] statusCode["+str(result.status_code)+"] result["+result.text+"]")    
    
    #RETURN RESULTS TO MAIN
    return result

if __name__ == "__main__" :

    #OS PID FOR TRACING
    pid = os.getpid()

    event = argparse.ArgumentParser(prog=appName+"v:"+appVersion, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    #NAGIOS MACRO VALUES WILL BE USED TO PROVIDE INPUT VIA THE NAGIOS COMMAND
    #event.add_argument(
    #    required=True,
    #    default=none,
    #    help="String(): "
    #)


    #  --type="Service",
    #  --lastservicestateid="$LASTSERVICEPROBLEMID$",
    #  --servicestateid="$SERVICESTATEID$",
    #  --serviceeventid="$SERVICEPROBLEMID$",
    #  --serviceproblemid="$SERVICEEVENTID$",
    #  --lastserviceeventid="$LASTSEVICEEVENTID$",
    #  --lastserviceproblemid="$LASTSERVICEPROBLEMID$",
    #  --servicedowntime=$SERVICEDOWNTIME$,
    #  --servicestatetype-$SERVICESTATETYPE$,
    #  --hostname="$HOSTNAME$",
    #  --summary="$SERVICEDESC$",
    #  --severity="INFO",
    #  --source="$HOSTNAME$",
    #  --component="MyComponent",
    #  --group="MyGroup",
    #  --class="MyClass",
    #  --customdetails="$SERVICEOUT$"

    event.add_argument(
        "--type",
        required=True,
        default="service",
        help="String(Notificatioin Type): Either Service or Host."
    )
    event.add_argument(
        "--lastservicestateid",
        required=True,
        default=None,
        help="INT(lastservicestateid): Numeric representation of the last service state observerd in Nagios (2,1,0,3)"
    )
    event.add_argument(
        "--servicestateid",
        required=True,
        default=None,
        help="INT(servicestateid): Numeric representation of the current service state observerd in Nagios (2,1,0,3)"
    )
    event.add_argument(
        "--serviceeventid",
        required=True,
        default=None,
        help="INT(serviceeventid): Unique identifier for the current service event id."
    )
    event.add_argument(
        "--serviceproblemid",
        required=True,
        default=None,
        help="INT(seviceproblemid): Unique identifier fir the current service problem id"
    )
    event.add_argument(
        "--lastserviceeventid",
        required=True,
        default=None,
        help="INT(lastserviceeventid): Unique identifier for the last service event id"
    )
    event.add_argument(
        "--lastserviceproblemid",
        required=True,
        default=None,
        help="INT(lastserviceproblemid): Unique id for the last service problem id."
    )
    event.add_argument(
        "--servicedowntime",
        required=True,
        default=None,
        help="INT(servicedowntimedepth): Range between 0-X with zero being equal to no scheduled interruption."
    )
    event.add_argument(
        "--servicestatetype",
        required=True,
        default=None,
        help="String(servicesatetype): String value of either HARD or SOFT. Hard states result when service checks have been checked a specified maximum number of times."
    )
    event.add_argument(
        "--hostname",
        required=True,
        default=None,
        help="String(Hostname): The hostname to act on behalf of in PagerDuty"
    )
    event.add_argument(
        "--summary",
        required=True,
        default=None,
        help="String(Summary): A high-level, text summary message of the event. Will be used to construct an alert's description."
    )
    event.add_argument(
        "--severity",
        required=True,
        default=None,
        help="String(Severity): How impacted the affected system is. Displayed to users in lists and influences the priority of any created incidents. (Info, Warning, Critical, Error_"
    )
    event.add_argument(
        "--source",
        required=True,
        default=None,
        help="String(Source): Specific human-readable unique identifier for the the problem. (Nagios Service Name/Host Alert)"
    )
    event.add_argument(
        "--component",
        required=True,
        default=None,
        help="String(Component):The part or component of the affected system that is broken. (Hardware, Resource, System, Service, Application)"
    )
    event.add_argument(
        "--group",
        required=True,
        default=None,
        help="String(Hostgroup): The name/list of names of groups for the origin system in Nagios"
    )
    event.add_argument(
        "--mclass",
        required=True,
        default=None,
        help="String(Class): The class/type of the event."
    )
    event.add_argument(
        "--customdetails",
        required=True,
        default=None,
        help="JSONString(ServiceOutput/LongServiceOutput): {'custom':details,'form':free}"
    )
    event.add_argument(
        "--debug",
        action="store_true",
        help="Boolean(StoreIfTrue): Set the flag to echo debug output to console and log."
    )

    #PARSE NAGIOS EVENT INPUT AND BUILD THE META ARRAY
    meta = event.parse_args()

    #DEAL WITH THE DEBUG
    if meta.debug:
        ch.setLevel(logging.DEBUG)
        fh.setLevel(logging.DEBUG)

    #PASS JUDGEMENT
    valid = makeJudgementCall(meta)
    
    if valid:
        #GET THE EVENT TYPE
        #etype = getEventType(meta)
        etype = pdEventType(meta)
        #PERFORM ACTION BASED ON EVENT TYPE
        triggerList = ['trigger','update']
        if etype in triggerList:
            #TRIGGER NEW INCIDNET
            trigger = handleEvent(etype, meta)
            logger.info(trigger.text)
        
        elif etype == "resolve":
            #SEND UPDATE EVENT
            resolve = handleEvent(etype, meta)
            logger.info(resolve.text)
        
        elif etype == "discard":
            #CATCHALL FOR DISCARD EVENTS, SHOULD NOT HAPPEN
            #LOG AND EXIT
            logger.info("pid["+str(os.getpid())+"] EventHandler received the \"discard\" event type.")
            sys.exit(2)
        else:
            #THE RETURNED EVENT TYPE IS UNKNOW AND HAS FALLEN THOGUH OUR FILTERSWE WILL EXIT WITH FAILURE AND LOG
            #HANDLER INPUT TO HELP WITH TROUBLESHOOTING.
            logger.error("pid["+str(os.getpid())+"] EventHandler Failed to determine the eventType from the handler input.")
            sys.exit()
    else:
        #WE SHOULD NOT BE HERE
        #HANDLER INPUT TO HELP WITH TROUBLESHOOTING.
        logger.critical("pid["+str(os.getpid())+"] EventHandler input failed validity judgement calls without exiting.")
        sys.exit()
