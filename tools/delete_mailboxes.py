#!/usr/bin/env python

# Author: Zhang Huangbin <zhb@iredmail.org>
# Purpose: Delete mailboxes which are scheduled to be removed.
#
# Notes: iRedAdmin will store maildir path of removed mail users in SQL table
#        `iredadmin.deleted_mailboxes` (LDAP backends) or
#        `vmail.deleted_mailboxes` (SQL backends).
#
# Usage: Either run this script manually, or run it with a daily cron job.
#
#   # python delete_mailboxes.py

import os
import sys
import logging
import shutil
import pwd
import web

os.environ['LC_ALL'] = 'C'

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/../'
sys.path.insert(0, rootdir)

from tools import ira_tool_lib
import settings

web.config.debug = ira_tool_lib.debug
logger = ira_tool_lib.logger

if '--debug' in sys.argv:
    logger.setLevel(logging.DEBUG)

# Delete if `deleted_mailboxes.delete_date` is null.
delete_null_date = False
if '--delete-null-date' in sys.argv:
    delete_null_date = True

def delete_record(conn, rid):
    try:
        conn.delete('deleted_mailboxes',
                    vars={'id': rid},
                    where='id = $id')
        return (True, )
    except Exception, e:
        return (False, repr(e))


def delete_mailbox(conn, record):
    rid = record.id
    username = str(record.username)
    maildir = record.maildir
    timestamp = str(record.timestamp)
    delete_date = record.delete_date

    # check directory
    if os.path.isdir(maildir):
        # Make sure directory is owned by vmail:vmail
        _dir_stat = os.stat(maildir)
        _dir_uid = _dir_stat.st_uid

        # Get uid/gid of vmail user
        owner = pwd.getpwuid(_dir_uid).pw_name
        if owner != 'vmail':
            logger.error('<<< ERROR >> Directory is not owned by `vmail` user: uid -> %d, user -> %s.' % (_dir_uid, owner))
            return False

        try:
            msg = 'Deleted mailbox (%s): %s.' % (username, maildir)
            msg += ' Account was deleted at %s.' % (timestamp)
            if delete_date:
                msg += ' Mailbox was scheduled to be removed on %s.' % (delete_date)
            else:
                msg += ' Mailbox was scheduled to be removed as soon as possible.'

            logger.info(msg)

            # Delete mailbox
            shutil.rmtree(maildir)

            # Log this deletion.
            ira_tool_lib.log_to_iredadmin(msg,
                                          admin='cron_delete_mailboxes',
                                          username=username,
                                          event='delete_mailboxes')
        except Exception, e:
            logger.error('<<< ERROR >> while deleting mailbox (%s -> %s): %s' % (username, maildir, repr(e)))

    # Delete record.
    delete_record(conn=conn, rid=rid)


# Establish SQL connection.
try:
    if settings.backend == 'ldap':
        conn = ira_tool_lib.get_db_conn('iredadmin')
    else:
        conn = ira_tool_lib.get_db_conn('vmail')
except Exception, e:
    sys.exit('<<< ERROR >>> Cannot connect to SQL database, aborted. Error: %s' % repr(e))

# Get pathes of all maildirs.
sql_where = 'delete_date <= %s' % web.sqlquote(web.sqlliteral('NOW()'))
if delete_null_date:
    sql_where = '(delete_date <= %s) OR (delete_date IS NULL)' % web.sqlquote(web.sqlliteral('NOW()'))

qr = conn.select('deleted_mailboxes', where=sql_where)

if qr:
    logger.info('Delete old mailboxes (%d in total).' % len(qr))
else:
    logger.debug('No mailbox is scheduled to be removed.')

    if not delete_null_date:
        logger.debug("To remove mailboxes with empty schedule date, please run this script with argument '--delete-null-date'.")

    sys.exit()

for r in list(qr):
    delete_mailbox(conn=conn, record=r)
