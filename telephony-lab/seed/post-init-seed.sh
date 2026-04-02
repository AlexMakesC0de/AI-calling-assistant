#!/bin/bash
# telephony-lab/seed/post-init-seed.sh
# Runs after FreePBX first-run install completes.
# Imports the seed database to restore extensions, ring groups,
# inbound routes, and settings so every 'docker compose up' starts
# with a working lab configuration.

SEED_SQL="/assets/seed/asterisk.sql"
MARKER="/data/.seed_imported"

# Skip if already seeded (idempotent)
if [ -f "$MARKER" ]; then
    echo "[seed] Already imported — skipping."
    exit 0
fi

# Skip if seed file is missing
if [ ! -f "$SEED_SQL" ]; then
    echo "[seed] No seed file found at $SEED_SQL — skipping."
    exit 0
fi

echo "[seed] Waiting for FreePBX install to finish..."
# The install creates /var/www/html/admin/index.php at the end
timeout=1800  # 30 minutes max
elapsed=0
while [ ! -f /var/www/html/admin/index.php ]; do
    sleep 10
    elapsed=$((elapsed + 10))
    if [ "$elapsed" -ge "$timeout" ]; then
        echo "[seed] Timed out waiting for FreePBX install."
        exit 1
    fi
done
echo "[seed] FreePBX installed. Waiting 30s for DB to settle..."
sleep 30

# Read actual DB credentials from freepbx.conf (may differ from env vars)
REAL_DB_USER=$(php -r "include '/etc/freepbx.conf'; echo \$amp_conf['AMPDBUSER'];" 2>/dev/null)
REAL_DB_PASS=$(php -r "include '/etc/freepbx.conf'; echo \$amp_conf['AMPDBPASS'];" 2>/dev/null)
REAL_DB_HOST=$(php -r "include '/etc/freepbx.conf'; echo \$amp_conf['AMPDBHOST'];" 2>/dev/null)
REAL_DB_NAME=$(php -r "include '/etc/freepbx.conf'; echo \$amp_conf['AMPDBNAME'];" 2>/dev/null)

# Fallback to env vars if PHP parsing failed
REAL_DB_USER="${REAL_DB_USER:-$DB_USER}"
REAL_DB_PASS="${REAL_DB_PASS:-$DB_PASS}"
REAL_DB_HOST="${REAL_DB_HOST:-$DB_HOST}"
REAL_DB_NAME="${REAL_DB_NAME:-$DB_NAME}"

echo "[seed] Importing seed database into $REAL_DB_NAME@$REAL_DB_HOST..."
mysql -u "$REAL_DB_USER" -p"$REAL_DB_PASS" -h "$REAL_DB_HOST" "$REAL_DB_NAME" < "$SEED_SQL"
rc=$?

if [ "$rc" -eq 0 ]; then
    echo "[seed] Database imported successfully."

    # Sync AMI password into manager.conf to match the DB value (amp111)
    AMI_PASS=$(mysql -u "$REAL_DB_USER" -p"$REAL_DB_PASS" -h "$REAL_DB_HOST" "$REAL_DB_NAME" \
        -sNe "SELECT value FROM freepbx_settings WHERE keyword='AMPMGRPASS';" 2>/dev/null)

    if [ -n "$AMI_PASS" ]; then
        sed -i "s/^secret = .*/secret = $AMI_PASS/" /etc/asterisk/manager.conf
        echo "[seed] AMI password synced to manager.conf."
    fi

    # Update amportal.conf
    if [ -f /etc/amportal.conf ]; then
        sed -i "s/^AMPMGRPASS=.*/AMPMGRPASS=$AMI_PASS/" /etc/amportal.conf
    fi

    # Install IVR greeting sound file
    GREETING_SRC="/assets/seed/ivr-greeting.ogg"
    GREETING_DST="/var/lib/asterisk/sounds/custom/ivr-greeting.ogg"
    if [ -f "$GREETING_SRC" ]; then
        mkdir -p /var/lib/asterisk/sounds/custom
        cp "$GREETING_SRC" "$GREETING_DST"
        chown asterisk:asterisk "$GREETING_DST"
        echo "[seed] IVR greeting installed."
    fi

    # Install custom dialplan (9999 → IVR with recording)
    printf '[from-internal-custom]\nexten => 9999,1,Answer()\n same => n,Set(__DIRECTION=INBOUND)\n same => n,Set(__FROM_DID=9999)\n same => n,Set(CDR(did)=9999)\n same => n,Gosub(sub-record-check,s,1(in,9999,force))\n same => n,Goto(ivr-1,s,1)\n' > /etc/asterisk/extensions_custom.conf

    # Enable recordingfile in CDR AMI events (for AMI listener)
    printf '[mappings]\nrecordingfile => recordingfile\n' > /etc/asterisk/cdr_manager_mapping_custom.conf
    chown asterisk:asterisk /etc/asterisk/cdr_manager_mapping_custom.conf

    # Allow AMI connections from Docker network (for ami-listener container)
    printf '[admin-docker]\nsecret = amp111\ndeny=0.0.0.0/0.0.0.0\npermit=172.16.0.0/255.240.0.0\nread = system,call,log,verbose,command,agent,user,config,dtmf,reporting,cdr,dialplan,originate,message\nwrite = system,call,log,verbose,command,agent,user,config,dtmf,reporting,cdr,dialplan,originate,message\nwritetimeout = 5000\n' > /etc/asterisk/manager_custom.conf
    chown asterisk:asterisk /etc/asterisk/manager_custom.conf

    # Reload Asterisk manager and FreePBX
    asterisk -rx "manager reload" 2>/dev/null
    fwconsole reload 2>/dev/null

    # Mark as done
    touch "$MARKER"
    echo "[seed] Seed complete. Extensions 1001, 1002, ring group 600, IVR ready."
else
    echo "[seed] ERROR: Database import failed (exit code $rc)."
    exit 1
fi
