 #!/bin/sh

. ./scripts/loadenv.sh

echo 'Running "auth_init.py"'
python3 ./scripts/auth_init.py --appid "$AUTH_APP_ID"
