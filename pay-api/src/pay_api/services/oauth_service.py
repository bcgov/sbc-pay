from pay_api.utils.enums import AuthHeaderType, ContentType
import json

import requests


class OAuthService:

    def post(self, endpoint, token, auth_header_type: AuthHeaderType, content_type: ContentType, data):
        print('<post')
        headers = {
            "Authorization": auth_header_type.value.format(token),
            "Content-Type": content_type.value
        }
        if content_type == ContentType.JSON:
            data = json.dumps(data)

        print('Endpoint : {}'.format(endpoint))
        print('headers : {}'.format(headers))
        print('data : {}'.format(data))

        response = requests.post(endpoint, data=data, headers=headers)
        print('response : {}'.format(response.text))
        response.raise_for_status()
        print('>post')
        return response

    def get(self):

        pass

    def put(self):
        pass

    def delete(self):
        pass
