#!/bin/bash
# telephony-lab/seed/fix-ami-password.sh
# Runs on EVERY container start (via /assets/custom-scripts/).
# Backgrounds itself and waits for Asterisk to be fully running,
# then syncs the AMI password across amportal.conf, manager.conf,
# and the DB. This solves the init-ordering problem where the
# tiredofit/freepbx image regenerates configs AFTER custom scripts.

(
    LOG_PREFIX="[fix-ami]"
    AMI_PASS="amp111"

    # Wait for Asterisk to be fully running (fwconsole start fires after us)
    timeout=300
    elapsed=0
    while ! asterisk -rx "core show version" >/dev/null 2>&1; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [ "$elapsed" -ge "$timeout" ]; then
            echo "$LOG_PREFIX Timed out waiting for Asterisk after ${timeout}s"
            exit 1
        fi
    done
    # Extra settle time for fwconsole reload to finish
    sleep 10

    echo "$LOG_PREFIX Asterisk is running — checking AMI password..."
    changed=0

    # 1. Fix amportal.conf
    if [ -f /etc/amportal.conf ]; then
        current=$(grep "^AMPMGRPASS=" /etc/amportal.conf 2>/dev/null | cut -d= -f2)
        if [ "$current" != "$AMI_PASS" ]; then
            sed -i "s/^AMPMGRPASS=.*/AMPMGRPASS=$AMI_PASS/" /etc/amportal.conf
            echo "$LOG_PREFIX Fixed amportal.conf (was: $current)"
            changed=1
        fi
    fi

    # 2. Fix manager.conf
    if [ -f /etc/asterisk/manager.conf ]; then
        mgr_current=$(grep "^secret = " /etc/asterisk/manager.conf 2>/dev/null | head -1 | awk '{print $3}')
        if [ "$mgr_current" != "$AMI_PASS" ]; then
            sed -i "s/^secret = .*/secret = $AMI_PASS/" /etc/asterisk/manager.conf
            echo "$LOG_PREFIX Fixed manager.conf (was: $mgr_current)"
            changed=1
        fi
    fi

    # 2b. Fix manager_custom.conf (admin-docker user for AMI listener)
    if [ -f /etc/asterisk/manager_custom.conf ]; then
        mgr_custom_current=$(grep "^secret = " /etc/asterisk/manager_custom.conf 2>/dev/null | head -1 | awk '{print $3}')
        if [ "$mgr_custom_current" != "$AMI_PASS" ]; then
            sed -i "s/^secret = .*/secret = $AMI_PASS/" /etc/asterisk/manager_custom.conf
            echo "$LOG_PREFIX Fixed manager_custom.conf (was: $mgr_custom_current)"
            changed=1
        fi
    fi

    # 3. Fix DB (freepbx_settings)
    DB_USER=$(php -r "include '/etc/freepbx.conf'; echo \$amp_conf['AMPDBUSER'];" 2>/dev/null)
    DB_PASS_DB=$(php -r "include '/etc/freepbx.conf'; echo \$amp_conf['AMPDBPASS'];" 2>/dev/null)
    DB_HOST=$(php -r "include '/etc/freepbx.conf'; echo \$amp_conf['AMPDBHOST'];" 2>/dev/null)
    DB_NAME=$(php -r "include '/etc/freepbx.conf'; echo \$amp_conf['AMPDBNAME'];" 2>/dev/null)

    if [ -n "$DB_USER" ] && [ -n "$DB_HOST" ]; then
        db_current=$(mysql -u "$DB_USER" -p"$DB_PASS_DB" -h "$DB_HOST" "$DB_NAME" \
            -sNe "SELECT value FROM freepbx_settings WHERE keyword='AMPMGRPASS';" 2>/dev/null)
        if [ "$db_current" != "$AMI_PASS" ]; then
            mysql -u "$DB_USER" -p"$DB_PASS_DB" -h "$DB_HOST" "$DB_NAME" \
                -e "UPDATE freepbx_settings SET value='$AMI_PASS' WHERE keyword='AMPMGRPASS';" 2>/dev/null
            echo "$LOG_PREFIX Fixed DB AMPMGRPASS (was: $db_current)"
            changed=1
        fi
    fi

    if [ "$changed" -eq 1 ]; then
        asterisk -rx "manager reload" 2>/dev/null
        echo "$LOG_PREFIX AMI password synced to $AMI_PASS and manager reloaded."
    else
        echo "$LOG_PREFIX All three locations already correct ($AMI_PASS) — no changes."
    fi
) &
echo "[fix-ami] Backgrounded AMI password sync (PID: $!)"
