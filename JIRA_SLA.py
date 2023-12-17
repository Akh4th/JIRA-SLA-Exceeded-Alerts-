from jira import JIRA
from datetime import datetime, timedelta
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import configparser

# Load configuration from config.ini
config = configparser.ConfigParser()
config.read('config.ini')

# JIRA configuration
JIRA_EMAIL = config.get('JIRA', 'email')
JIRA_API_TOKEN = config.get('JIRA', 'api_token')
JIRA_SERVER = config.get('JIRA', 'server')
JIRA_PROJECT = config.get('JIRA', 'project')
JIRA_STATUS = config.get('JIRA', 'status')
jira = JIRA(basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN), server=JIRA_SERVER)
jql_str = f"project = {JIRA_PROJECT} AND status = '{JIRA_STATUS}'"
tickets = jira.search_issues(jql_str, maxResults=False)

# SLA configuration
WEEK_MASK = config['DEFAULT']['WEEK_MASK']
SLA = {
    'Low': timedelta(days=int(config.get('SLA', 'low'))),
    'Medium': timedelta(days=int(config.get('SLA', 'medium'))),
    'High': timedelta(days=int(config.get('SLA', 'high'))),
    'Critical': timedelta(seconds=int(config.get('SLA', 'critical').split(':')[-1]))
}

# Email configuration
FROM_EMAIL = config.get('Email', 'from_email')
APP_PASSWORD = config.get('Email', 'app_password')
TO_EMAIL = config.get('Email', 'to_email').split(', ')

# SLA tracking
msg = ""
exceeded = 0
included = []


def send_email(data, number):
    if number == 0:
        print("No tickets have exceeded their SLA\nWell played !")
        return
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = ', '.join(TO_EMAIL)
    msg['Subject'] = f"{number} Tickets Exceeded the SLA !"
    msg.attach(MIMEText(data, 'plain'))
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(FROM_EMAIL, APP_PASSWORD)
    server.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
    server.quit()
    print("SENT")


for ticket in tickets:
    created_date = ticket.fields.created
    created_datetime = datetime.strptime(created_date, '%Y-%m-%dT%H:%M:%S.%f%z')
    priority = ticket.fields.priority.name
    current_time = datetime.now(created_datetime.tzinfo)
    elapsed_time = current_time - created_datetime
    if priority in ['Low', 'Medium', 'High']:
        sla_end_date_np = np.busday_offset(created_datetime.date(), int(SLA[priority].days), roll='forward', weekmask=WEEK_MASK)
        sla_end_date = sla_end_date_np.astype('M8[D]').astype('O')
        sla_end_datetime = datetime.combine(sla_end_date, created_datetime.time(), tzinfo=created_datetime.tzinfo)
    else:
        sla_end_datetime = created_datetime + SLA[priority]
    if current_time > sla_end_datetime:
        if ticket.key not in included:
            included.append(ticket.key)
            url = f"{JIRA_SERVER}/browse/{ticket.key}"
            exceeded += 1
            msg = msg + f"{ticket.key} with {priority} priority has passed the SLA ({priority} == {SLA[priority]}).\n URL : {url}.\nCreated on {created_datetime}\n Issue : {ticket.fields.summary}\n Description : {ticket.fields.description}\n\n"

send_email(msg, exceeded)

