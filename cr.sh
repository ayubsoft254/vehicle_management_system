#!/bin/bash

CERT_FILE="${1:-SafaricomPublicKey.cer}"

if [ ! -f "$CERT_FILE" ]; then
  echo "Certificate file not found: $CERT_FILE"
  echo "Usage: ./generate_mpesa_credential.sh path/to/SafaricomPublicKey.cer"
  exit 1
fi

read -s -p "Enter M-Pesa initiator password: " MPESA_PASSWORD
echo

if [ -z "$MPESA_PASSWORD" ]; then
  echo "Password cannot be empty."
  exit 1
fi

SECURITY_CREDENTIAL=$(printf "%s" "$MPESA_PASSWORD" | openssl pkeyutl -encrypt -certin -inkey "$CERT_FILE" | base64 -w 0)

if [ $? -ne 0 ]; then
  echo "Encryption failed. Trying older OpenSSL method..."
  SECURITY_CREDENTIAL=$(printf "%s" "$MPESA_PASSWORD" | openssl rsautl -encrypt -inkey "$CERT_FILE" -certin | base64 -w 0)
fi

echo
echo "MPESA_SECURITY_CREDENTIAL=$SECURITY_CREDENTIAL"