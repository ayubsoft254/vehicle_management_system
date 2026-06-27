#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_FILE="${1:-$SCRIPT_DIR/SafaricomPublicKey.cer}"
ENV_FILE="${2:-$SCRIPT_DIR/.env}"
TEMP_CERT=""
TEMP_PASS=""

cleanup() {
  [ -n "$TEMP_CERT" ] && rm -f "$TEMP_CERT"
  [ -n "$TEMP_PASS" ] && rm -f "$TEMP_PASS"
}
trap cleanup EXIT

# If no cert file, ask user to paste the PEM content
if [ ! -f "$CERT_FILE" ]; then
  echo "Certificate file '$CERT_FILE' not found."
  echo
  echo "Paste your Safaricom public key certificate (including -----BEGIN CERTIFICATE----- lines),"
  echo "then press Enter and Ctrl+D when done:"
  echo

  TEMP_CERT=$(mktemp /tmp/safaricom_cert_XXXXXX.cer)
  cat > "$TEMP_CERT"

  if [ ! -s "$TEMP_CERT" ]; then
    echo "No certificate content provided. Exiting."
    exit 1
  fi

  CERT_FILE="$TEMP_CERT"
fi

read -s -p "Enter M-Pesa initiator password: " MPESA_PASSWORD
echo

if [ -z "$MPESA_PASSWORD" ]; then
  echo "Password cannot be empty."
  exit 1
fi

read -s -p "Confirm M-Pesa initiator password: " MPESA_PASSWORD_CONFIRM
echo

if [ "$MPESA_PASSWORD" != "$MPESA_PASSWORD_CONFIRM" ]; then
  echo "Passwords do not match."
  exit 1
fi

echo "Encrypting..."

# Write password to a temp file (required by openssl -in flag)
TEMP_PASS=$(mktemp /tmp/mpesa_pass_XXXXXX.txt)
printf "%s" "$MPESA_PASSWORD" > "$TEMP_PASS"

SECURITY_CREDENTIAL=$(openssl rsautl -encrypt -inkey "$CERT_FILE" -certin -in "$TEMP_PASS" | base64)

if [ $? -ne 0 ] || [ -z "$SECURITY_CREDENTIAL" ]; then
  echo "Encryption failed. Make sure the certificate is a valid Safaricom public key."
  exit 1
fi

# Strip any newlines from base64 output
SECURITY_CREDENTIAL=$(echo "$SECURITY_CREDENTIAL" | tr -d '\n')

echo
echo "MPESA_SECURITY_CREDENTIAL=$SECURITY_CREDENTIAL"
echo

# Save to .env file
if [ -f "$ENV_FILE" ]; then
  if grep -q "^MPESA_SECURITY_CREDENTIAL=" "$ENV_FILE"; then
    sed -i "s|^MPESA_SECURITY_CREDENTIAL=.*|MPESA_SECURITY_CREDENTIAL=$SECURITY_CREDENTIAL|" "$ENV_FILE"
    echo "Updated MPESA_SECURITY_CREDENTIAL in $ENV_FILE"
  else
    echo "MPESA_SECURITY_CREDENTIAL=$SECURITY_CREDENTIAL" >> "$ENV_FILE"
    echo "Appended MPESA_SECURITY_CREDENTIAL to $ENV_FILE"
  fi
else
  echo "MPESA_SECURITY_CREDENTIAL=$SECURITY_CREDENTIAL" > "$ENV_FILE"
  echo "Created $ENV_FILE with MPESA_SECURITY_CREDENTIAL"
fi
