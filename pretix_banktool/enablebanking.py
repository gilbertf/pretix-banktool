import json
import os
import sys
import click
import uuid
from datetime import datetime, timezone, timedelta
from pprint import pprint
from urllib.parse import urlparse, parse_qs
import configparser

import requests
import jwt as pyjwt
from .config import validate_config

class EnableBanking:
    API_ORIGIN = "https://api.enablebanking.com"
    debug = False

    def __init__(self, config):
        self.config = config

        iat = int(datetime.now().timestamp())
        jwt_body = {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": iat,
            "exp": iat + 3600,
        }

        jwt = pyjwt.encode(
            jwt_body,
            open(self.config["enablebanking"]["keyfile"], "rb").read(),
            algorithm="RS256",
            headers={"kid": self.config["enablebanking"]["applicationId"]},
        )
        
        self.base_headers = {"Authorization": f"Bearer {jwt}"}


    def register(self, configfile):
            #Retrieve app details
            r = requests.get(f"{self.API_ORIGIN}/application", headers=self.base_headers)
            if r.status_code == 200:
                app = r.json()
                if self.debug:
                    print("Application details:")
                    pprint(app)
            else:
                print(f"Error response {r.status_code}:", r.text)
                return
        
            # Starting authorization
            body = {
                "access": {
                    "valid_until": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
                },
                "aspsp": {"name": self.config['enablebanking']['aspspName'], "country": self.config['enablebanking']['aspspCountry']},
                "state": str(uuid.uuid4()),
                "redirect_url": app["redirect_urls"][0],
                "psu_type": "business",
            }
            r = requests.post(f"{self.API_ORIGIN}/auth", json=body, headers=self.base_headers)
            if r.status_code == 200:
                auth_url = r.json()["url"]
                print(f"To authenticate open URL {auth_url}")
            else:
                print(f"Error response {r.status_code}:", r.text)
                return
        
            ## Reading auth code and creating user session
            redirected_url = input("Paste here the URL you have been redirected to: ")
            auth_code = parse_qs(urlparse(redirected_url).query)["code"][0]
            
            r = requests.post(f"{self.API_ORIGIN}/sessions", json={"code": auth_code}, headers=self.base_headers)
            if r.status_code == 200:
                session = r.json()
                if self.debug:
                    print("New user session has been created:")
                    pprint(session)
            else:
                print(f"Error response {r.status_code}:", r.text)
                return
        
            sessionId = session["session_id"]

            config = self.config
            config["enablebanking"]["sessionId"] = sessionId
            
            if self.debug:
                print("SessionID:", sessionId)

            with open(configfile, 'w') as cf:
                config.write(cf)
        
            click.echo(click.style('Saved new session id to configfile', fg='green'))


    def getPayload(self):
        click.echo('Retrieving transactions from enable banking service')

        # Requesting application details
        r = requests.get(f"{self.API_ORIGIN}/application", headers=self.base_headers)
        if r.status_code == 200:
            app = r.json()
            if self.debug:
                print("Application details:")
                pprint(app)
        else:
            print(f"Error response {r.status_code}:", r.text)
            return
        
        # Fetching session details
        r = requests.get(f"{self.API_ORIGIN}/sessions/{self.config["enablebanking"]["sessionId"]}", headers=self.base_headers)
        if r.status_code == 200:
            if self.debug:
                print("Session data:")
                pprint(r.json())
        else:
            print(f"Error response {r.status_code}:", r.text)
            return
        
        session = r.json()
        account_uid = session["accounts"][0]
        
        ## Retrieving account transactions (since 90 days ago)
        query = {
            "date_from": (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat(),
        }
        continuation_key = None
        data = list()
        while True:
            if continuation_key:
                query["continuation_key"] = continuation_key
            r = requests.get(
                f"{self.API_ORIGIN}/accounts/{account_uid}/transactions",
                params=query,
                headers=self.base_headers,
            )
            if r.status_code == 200:
                resp_data = r.json()
                data.append(resp_data)
                if self.debug:
                    print("Transactions:")
                    pprint(resp_data["transactions"])
                continuation_key = resp_data.get("continuation_key")
                if not continuation_key:
                    print("No continuation key. All transactions were fetched")
                    break
                print(f"Going to fetch more transactions with continuation key {continuation_key}")
            else:
                print(f"Error response {r.status_code}:", r.text)
                return None
    
        if len(data) == 0:
            return None
        
        transactions = list()
        try:
            for d in data:
                if not "transactions" in d:
                    print("Missing transactions sections in retrieved data")
                    continue
                for e in d["transactions"]:
                    if not "transaction_amount" in e or e["transaction_amount"] == None or not "amount" in e["transaction_amount"]:
                        print("Missing transaction amount in retrieved data")
                        continue
                    amount = e["transaction_amount"]["amount"]

                    if not "remittance_information" in e:
                        print("Missing remittance_information in retrieved data")
                        continue
                    reference = ", ".join(e["remittance_information"])

                    if not "debtor_account" in e or e["debtor_account"] == None or not "iban" in e["debtor_account"]:
                        print("Missing iban in retrieved data")
                        payer_iban = None
                    else:
                        payer_iban = e["debtor_account"]["iban"]

                    if not "debtor" in e or e["debtor"] == None or not "name" in e["debtor"]:
                        print("Missing debtor name in retrieved data")
                        payer_name = None
                    else:
                        payer_name = e["debtor"]["name"]

                    if not "booking_date" in e:
                        print("Missing booking_date in retrieved data")
                        continue
                    date = e["booking_date"]

                    if self.debug:
                        print(amount, reference, payer_iban, payer_name, date)

                    tx = {
                            'amount': amount,
                            'reference': reference,
                            'payer': (payer_name or '') + ' - ' + (payer_iban or ''),
                            'date': date,
                    }
                    transactions.append(tx)
                    
                    if self.debug:
                        print(tx)
        except Exception as e:
            print(e)
        
        if len(transactions) == 0:
            return None
        
        payload = {
                'event': None,
                'transactions': transactions
                }
        
        return payload
