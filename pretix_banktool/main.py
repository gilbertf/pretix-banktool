import configparser
from urllib.parse import urljoin

import click
from pretix_banktool.upload import upload_transactions

from .config import validate_config
from .testing import test_fints, test_pretix
from .enablebanking import EnableBanking
from .pretix import upload as pretix_upload
from .pretix import listUploads as pretix_list

@click.group()
def main():
    pass


@main.command()
@click.argument('configfile', type=click.Path(exists=True))
def register(configfile):
    config = configparser.ConfigParser()
    config.read(configfile)
    validate_config(config, ignoreSessionIdMissing = True)
    if config["banktool"]["type"] == "enablebanking":
        if "sessionid" in config["enablebanking"]:
            click.echo(click.style('You already have a sessionid in your config. Running register is not required.', fg='red'))
            return
        click.echo(click.style('Procedure to register bank account to enablebanking service', fg='green'))
        eb = EnableBanking(config)
        eb.register(configfile)
    else:
        click.echo(click.style('Register is only neccessary when using enablebanking', fg='red'))


@main.command()
@click.argument('configfile', type=click.Path(exists=True))
@click.option('--fints/--no-fints', default=True, help='Test FinTS connection')
@click.option('--pretix/--no-pretix', default=True, help='Test pretix connection')
def test(configfile, fints, pretix):
    config = configparser.ConfigParser()
    config.read(configfile)
    validate_config(config)
    if config['banktool']['type'] == 'enablebanking':
        click.echo(click.style('Testing enablebanking is not supported', fg='red'))
    if config['banktool']['type'] == 'fints' and fints:
        test_fints(config)
    if pretix:
        test_pretix(config)


@main.command()
@click.argument('configfile', type=click.Path(exists=True))
@click.option('--last', default=1, help='Only show last n bank import on pretix instance')
@click.option('--transactions/--no-transactions', default=False, help='Show individual transactions')
def listuploads(configfile, last, transactions):
    config = configparser.ConfigParser()
    config.read(configfile)
    validate_config(config)
    pretix_list(config, last, transactions)

@main.command()
@click.argument('configfile', type=click.Path(exists=True))
@click.option('--days', default=30, help='Number of days to go back.')
@click.option('--pending/--no-pending', default=False, help='Include pending transactions.')
@click.option('--bank-ids/--no-bank-ids', default=False, help='Include transaction IDs given by bank.')
@click.option('--ignore', help='Ignore all references that match the given regular expression. '
                               'Can be passed multiple times.', multiple=True)
def upload(configfile, days, pending, bank_ids, ignore):
    config = configparser.ConfigParser()
    config.read(configfile)
    validate_config(config)
    if config['banktool']['type'] == 'enablebanking':
        click.echo(click.style('Ignoring all given parameters. Not supported for enable banking at the moment', fg='red'))
        eb = EnableBanking(config)
        payload = eb.getPayload()
        if payload != None:
            pretix_upload(config, payload)
    elif config['banktool']['type'] == 'fints':
        upload_transactions(config, days, pending, bank_ids, ignore)


@main.command()
@click.option('--type', type=click.Choice(['fints', 'enablebanking']), default='fints')
def setup(type):
    click.echo(click.style('Welcome to the pretix-banktool setup!', fg='green'))

    if type == 'fints':
        click.echo('You will now be prompted all information required to setup a FinTS account for pretix.')
        click.echo('')
        click.echo(click.style('Banking information', fg='blue'))
        blz = click.prompt('Your bank\'s BLZ')
        iban = click.prompt('Your account IBAN')
        endpoint = click.prompt('Your bank\'s FinTS endpount URL')
        username = click.prompt('Your online-banking username')
        click.echo(click.style('WARNING: If you enter your PIN here, it will be stored in clear text on your disk. '
                               'If you leave it empty, you will instead be asked for it every time.', fg='yellow'))
        pin = click.prompt('Your online-banking PIN', hide_input=True, default='', show_default=False)
    elif type == 'enablebanking':
        click.echo('You will now be prompted all information required to setup a Enable Banking account for pretix.')
        click.echo('')
        click.echo(click.style('Enable Banking authentication', fg='blue'))
        keyFile = click.prompt('Path to key file')
        appId = click.prompt('Application id')

        if len(appId) != 36:
            click.echo(click.style('Invalid application id length, expected 36 characters', fg='red'))
            return
        try:
            f = open(keyFile, "rb")
            b = f.read()
            f.close()
            if len(b) != 3271:
                click.echo(click.style('Invalid key file, expected 3271 bytes', fg='red'))
                return
        except:
            click.echo(click.style('Unable to read keyfile', fg='red'))
            return
        
        click.echo('Please specify your banking details, see https://enablebanking.com/open-banking-apis')
        aspspName = click.prompt('ASPSP Name (e.g. Förde Sparkasse)')
        aspspCountry = click.prompt('ASPSP country code (e.g. DE)')
        
    click.echo('')
    click.echo(click.style('pretix information', fg='blue'))
    api_server = click.prompt('pretix Server', default='https://pretix.eu/')
    api_organizer = click.prompt('Short name of your organizer account', type=click.STRING)
    click.echo('You will now need an API key. If you do not have one yet, you can create one as part of a team here:')
    click.echo(urljoin(api_server, '/control/organizer/{}/teams'.format(api_organizer)))
    click.echo('The key needs to created for a team with the permissions "can view orders" and "can change orders" '
               'for all events that you want to match orders with.')
    api_key = click.prompt('API key')

    click.echo('')
    click.echo(click.style('Other information', fg='blue'))
    filename = click.prompt('Configuration file', default=api_organizer + '.cfg', type=click.Path(exists=False))

    config = configparser.ConfigParser()
    config['banktool'] = {
        'type': type
    }
    if type == 'fints':
        config['fints'] = {
            'blz': blz,
            'endpoint': endpoint,
            'username': username,
            'iban': iban,
            'pin': pin
        }
    elif type == 'enablebanking':
        config['enablebanking'] = {
            'keyFile': keyFile,
            'applicationId': appId,
            'aspspName': aspspName,
            'aspspCountry': aspspCountry
        }
    config['pretix'] = {
        'server': api_server,
        'organizer': api_organizer,
        'key': api_key
    }
    with open(filename, 'w') as configfile:
        config.write(configfile)

    click.echo('')
    click.echo(click.style('Configuration file created!', fg='green'))
    
    if type == "fints":
        click.echo(click.style('Please note that your pin has been saved to the file in plain text. Make sure to secure '
                           'the file appropriately.', fg='red'))
    elif type == "enablebanking":
        register(configfile = configfile, type = "enablebanking")

    click.echo('')
    click.echo('You can now run')
    click.echo('    pretix-banktool test %s' % filename)
    click.echo('to test the connection to your bank account.')
