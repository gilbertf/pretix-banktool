import click
import requests
from pretix_banktool.config import get_endpoint
from requests import RequestException
import sys

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
