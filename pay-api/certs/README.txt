These are for WAM/IDIM pay.gov.bc.ca they solve the local cert issue that pops up. 
Contact PAYBC/CAS if this has expired.
These are public certs without private keys.
EG. openssl s_client -connect pay.gov.bc.ca:443 -showcerts
ends up verify error:num=20:unable to get local issuer certificate

DEPRECATION NOTICE:
- root.cer and inter.cer are DEPRECATED and will be removed after Nov 24, 2025
- Use root_2025.cer and inter_2025.cer going forward
- Both certificate sets are currently installed to ensure smooth transition

Local development (WSL2 Ubuntu tested) can be used for these with:

cat root.cer | sudo tee /usr/local/share/ca-certificates/root.crt
sudo update-ca-certificates

cat inter.cer | sudo tee /usr/local/share/ca-certificates/inter.crt
sudo update-ca-certificates

and setting environment variable to:
   "REQUESTS_CA_BUNDLE": "/etc/ssl/certs/ca-certificates.crt"
