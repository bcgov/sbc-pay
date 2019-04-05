import base64
import requests
import logging


class PayBcService:
    # TODO get all these values from config map
    client_id = 'n4VoztjSBNfNWIi0Khxu1g..'
    client_secret = '2bz-Sc2q5xmUO9nUORFo6g..'
    paybc_base_url = 'https://heineken.cas.gov.bc.ca:7019/ords/cas'

    def create_invoice(self, invoice_request):
        print('<Inside create invoice')
        token_response = self.get_token()
        token_response = token_response.json()
        print("Bearer token : {}".format(token_response.get('access_token')))
        party = self.create_party(token_response, invoice_request)
        account = self.create_account(token_response, party)
        site = self.create_site(token_response, account, invoice_request)
        invoice = self.create_paybc_invoice(token_response, site, invoice_request)
        print('>Inside create invoice')
        return invoice

    def create_party(self, token_response, invoice_request):
        print('<Creating party Record')
        party_url = self.paybc_base_url + '/cfs/parties'
        print('party_url : {}'.format(party_url))
        party = {
            "customer_name": invoice_request.get('entity_name')
        }
        print('party : {}'.format(party))

        headers = {
            "Authorization": "Bearer {}".format(token_response.get('access_token')),
            "Content-Type": "application/json"
        }
        print('headers : {}'.format(headers))

        party_response = requests.post(party_url, data=party, headers=headers)
        print('party_response : {}'.format(party_response))
        print('>Creating party Record')
        return party_response.json()

    def create_account(self, token_response, party):
        print('<Creating account Record')
        account_url = self.paybc_base_url + '/cfs/parties/{}/accs'.format(party.get('party_number'))
        account = {
            "party_number": party.get('party_number'),
            "account_description": party.get('customer_name')
        }
        headers = {
            "Authorization": "Bearer {}".format(token_response.get('access_token')),
            "Content-Type": "application/json"
        }

        account_response = requests.post(account_url, data=account, headers=headers)
        print('account_response : {}'.format(account_response))
        print('>Creating party Record')
        return account_response.json()

    def create_site(self, token_response, account, invoice_request):
        print('<Creating site ')
        site_url = self.paybc_base_url + '/cfs/parties/{}/accs/sites'.format(account.get('party_number'))
        account = {
            "party_number": account.get('party_number'),
            "account_description": invoice_request.get('entity_name')
        }
        headers = {
            "Authorization": "Bearer {}".format(token_response.get('access_token')),
            "Content-Type": "application/json"
        }

        site_response = requests.post(site_url, data=account, headers=headers)
        print('site_response : {}'.format(site_response))
        print('>Creating site ')
        return site_response.json()

    def create_contact(self, token_response, site, invoice_request):
        print('<Creating contact')
        contact_url = self.paybc_base_url + '/cfs/parties/{}/accs/sites/conts'.format(site.get('party_number'))
        contact = {
            "party_number": site.get('party_number'),
            "account_number": site.get('account_number'),
            "site_number": site.get('site_number'),
            "first_name": invoice_request.get('contact_first_name'),
            "last_name": invoice_request.get('contact_last_name')
        }
        headers = {
            "Authorization": "Bearer {}".format(token_response.get('access_token')),
            "Content-Type": "application/json"
        }

        contact_response = requests.post(contact_url, data=contact, headers=headers)
        print('contact_response : {}'.format(contact_response))
        print('>Creating contact')
        return contact_response.json()

    def create_paybc_invoice(self, token_response, site, invoice_request):
        print('<Creating PayBC Invoice Record')
        site_url = self.paybc_base_url + '/cfs/parties/{}/accs/sites'.format(site.get('party_number'))
        account = {
            "party_number": site.get('party_number'),
            "account_description": invoice_request.get('entity_name')
        }
        headers = {
            "Authorization": "Bearer {}".format(token_response.get('access_token')),
            "Content-Type": "application/json"
        }

        site_response = requests.post(site_url, data=account, headers=headers)
        print('site_response : {}'.format(site_response))
        print('>Creating PayBC Invoice Record')
        return site_response.json()

    def get_token(self):
        print('<Getting token')
        token_url = self.paybc_base_url + '/oauth/token'

        basic_auth_encoded = base64.b64encode(bytes(self.client_id + ':' + self.client_secret, "utf-8")).decode('utf-8')
        print('Auth Header : {}'.format(basic_auth_encoded))
        headers = {
            "Authorization": "Basic {}".format(basic_auth_encoded),
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = "grant_type=client_credentials"
        token_response = requests.post(token_url, data=data, headers=headers)
        print('token_response : {}'.format(token_response.content))
        print('>Getting token')
        return token_response

