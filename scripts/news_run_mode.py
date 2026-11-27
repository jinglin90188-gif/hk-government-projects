"""News runs at 07:00 UTC / 15:00 Hong Kong; accept legacy queued events."""
import os


def mode(event, schedule='', requested=''):
    if event == 'schedule':
        return {'projects': schedule == '0 8 * * *', 'news': schedule in ('0 7 * * *','0 14 * * *')}
    if event == 'workflow_dispatch':
        return {'projects': requested in ('', 'all', 'projects'), 'news': requested in ('', 'all', 'news')}
    return {'projects': True, 'news': True}


if __name__ == '__main__':
    for key, value in mode(os.environ.get('EVENT_NAME'), os.environ.get('SCHEDULE'), os.environ.get('RUN_MODE')).items():
        print(key + '=' + str(value).lower())
