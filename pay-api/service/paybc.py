import base64
import requests


class PayBcService:

    def create_invoice(self):
        # TODO get all these values from config map
        token_response = self.get_token()
        print("Bearer token : {}".format(token_response.access_token))
        
        return

    @staticmethod
    def get_token():
        client_id = 'n4VoztjSBNfNWIi0Khxu1g..'
        client_secret = '2bz-Sc2q5xmUO9nUORFo6g..'
        token_url = 'https://heineken.cas.gov.bc.ca:7019/ords/cas/oauth/token'

        basic_auth_encoded = base64.b64encode(bytes(client_id + ':' + client_secret, "utf-8"))
        print(basic_auth_encoded)
        headers = {
            "Authorization": "Basic {}".format(basic_auth_encoded),
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = "grant_type=client_credentials"
        token_response = requests.post(token_url, data=data, headers=headers)
        print(token_response)
        return token_response

