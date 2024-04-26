
# SFTP Poller project

Polls the SFTP folder and if a settlement file is found , uploads to minio and sends a pubsub message.

## Openshift commands


oc process -f ftp-poller-build.json |oc create -f -

oc process -f ftp-poller-deploy.json |oc create -f -

## Config maps 

Two config maps are needed for running the project.

ftp-poller-dev-cron-configuration
ftp-poller-dev-sftp-configuration



## How to generate an SSH key

The SFTP server supports only rsa key with 2048 length

> ssh-keygen -t rsa -b 2048 -C 'BC Registries Test_env'

When asked the location , give any custom folder where the keys has to be stored.
Give a passphrase as well.

Incase to verify the private key with public key ,  use the following command which will output the public key and comparisons can be made.

> ssh-keygen -y -f private_key

## How to verify CAS SFTP connectivity from openshift

login to some sftp supported container [need a user who can execute sftp]. Jenkins has such container

Commands

> oc rsync key jenkins-pod-name:/var/lib/origin/key/

> sftp -i priv_key user_name@server

### to run in debug mode

sftp ---vvv -o "IdentityFile= priv_key" user_name@server


## Code snippet to try the sftp from python terminal

```
import os 
import paramiko
from pysftp import Connection, CnOpts
from base64 import b64decode,decodebytes


sft_credentials = {
     'username': os.getenv('CAS_SFTP_USER_NAME'),
      'private_key': os.getenv('BCREG_FTP_PRIVATE_KEY_LOCATION'),
      'private_key_pass': os.getenv('BCREG_FTP_PRIVATE_KEY_PASSPHRASE')
  }

cnopts = CnOpts()
ftp_host_key_data = os.getenv('CAS_SFTP_HOST_KEY').encode()
key = paramiko.RSAKey(data=decodebytes(ftp_host_key_data))
sftp_host: str = os.getenv('CAS_SFTP_HOST')
cnopts.hostkeys.add(sftp_host, 'ssh-rsa', key)
sftp_port=22	
sftp_connection = Connection(host=sftp_host, **sft_credentials, cnopts=cnopts, port=sftp_port)
sftp_connection.listdir()


```

## How to get the CAS SFT servers public key

> ssh-keyscan server.gov.bc.ca

this will print the public key. Store the string after ssh-rsa to the ftp-poller configurations.

## For local SFTP testing 

https://hub.docker.com/r/atmoz/sftp

docker run -p 22:22 -d atmoz/sftp foo:pass:::upload
