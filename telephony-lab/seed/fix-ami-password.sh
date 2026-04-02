#!/bin/bash
# telephony-lab/seed/fix-ami-password.sh
# Runs on EVERY container start (via /assets/custom-scripts/).
# Fixes the AMI password mismatch caused by the tiredofit/freepbx
# image regenerating /etc/amportal.conf with a random password.

AMI_PASS="amp111"

# Wait for FreePBX to be installed
if [ ! -f /var/www/html/admin/index.php ]; then
    echo "[fix-ami] FreePBX not installed yet — skipping (seed script will handle it)."
    exit 0
fi

# Wait for amportal.conf to exist (image may still be writing it)
timeout=120
elapsed=0
while [ ! -f /etc/amportal.conf ]; do
    sleep 5
    elapsed=$((elapsed + 5))
    if [ "$elapsed" -ge "$timeout" ]; then
        echo "[fix-ami] No amportal.conf found after ${timeout}s — skipping."
        exit 0
    fi
done
# Give the image a moment to finish writing the file
sleep 5

changed=0

# Fix amportal.conf
current=$(grep "^AMPMGRPASS=" /etc/amportal.conf 2>/dev/null | cut -d= -f2)
if [ "$current" != "$AMI_PASS" ]; then
    sed -i "s/^AMPMGRPASS=.*/AMPMGRPASS=$AMI_PASS/" /etc/amportal.conf
    echo "[fix-ami] Fixed AMPMGRPASS in amportal.conf (was: $current)"
    changed=1
fi

# Fix manager.conf
if [ -f /etc/asterisk/manager.conf ]; then
    mgr_current=$(grep "^secret = " /etc/asterisk/manager.conf 2>/dev/null | head -1 | awk '{print $3}')
    if [ "$mgr_current" != "$AMI_PASS" ]; then
        sed -i "s/^secret = .*/secret = $AMI_PASS/" /etc/asterisk/manager.conf
        echo "[fix-ami] Fixed secret in manager.conf (was: $mgr_current)"
        changed=1
    fi
fi

if [ "$changed" -eq 1 ]; then
    # Reload Asterisk manager to pick up the change
    asterisk -rx "manager reload" 2>/dev/null
    echo "[fix-ami] AMI password synced to $AMI_PASS and manager reloaded."
else
    echo "[fix-ami] AMI password already correct ($AMI_PASS) — no changes needed."
fi
