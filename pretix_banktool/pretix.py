import click
import requests
from pretix_banktool.config import get_endpoint
from requests import RequestException
import sys
import json

def upload(config, payload):
    click.echo('Uploading transactions to pretix instance')
    try:
        r = requests.post(get_endpoint(config), headers={
            'Authorization': 'Token {}'.format(config['pretix']['key'])
        }, json=payload, verify=not config.getboolean('pretix', 'insecure', fallback=False))
        if r.status_code == 201:
            click.echo(click.style('Job uploaded.', fg='green'))
        else:
            click.echo(click.style('Invalid response code: %d' % r.status_code, fg='red'))
            click.echo(r.text)
            sys.exit(2)
    except (RequestException, OSError) as e:
        click.echo(click.style('Connection error: %s' % str(e), fg='red'))
        sys.exit(2)
    except ValueError as e:
        click.echo(click.style('Could not read response: %s' % str(e), fg='red'))
        sys.exit(2)

def listUploads(config, last, transactions):
    def parseResponse(r):
        d = json.loads(r.text)
        c = int(d["count"])
        for i, e in enumerate(d["results"]):
            if i < c - last:
                continue
            new = 0
            names = list()
            if e != None and "transactions" in e:
                for t in e["transactions"]:
                    if t["state"] == "valid":
                        new += 1
                        names.append(t["payer"])
                print("Import", e["id"])
                print(" "*3, new, "new payments")
                if transactions and len(names) > 0:
                    print(" "*3,"Transactions:", ", ".join(names))
                print() #Empty line
            else:
                print("Invalid dataset", e)
    
    click.echo('Requesting banking imports from server...')
    try:
        r = requests.get(get_endpoint(config), headers={'Authorization': 'Token {}'.format(config['pretix']['key'])})
        if r.status_code == 200:
            parseResponse(r)
        else:
            click.echo(click.style('Invalid response code: %d' % r.status_code, fg='red'))
            click.echo(r.text)
            sys.exit(2)
    except (RequestException, OSError) as e:
        click.echo(click.style('Connection error: %s' % str(e), fg='red'))
        sys.exit(2)
    except ValueError as e:
        click.echo(click.style('Could not read response: %s' % str(e), fg='red'))
        sys.exit(2)