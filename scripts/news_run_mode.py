"""Keep the 08:00 project run independent from the 14:00 news run."""
import os


def mode(event, schedule='', requested=''):
    if event == 'schedule':
        return {'projects': schedule == '0 8 * * *', 'news': schedule == '0 14 * * *'}
    if event == 'workflow_dispatch':
        return {'projects': requested in ('', 'all', 'projects'), 'news': requested in ('', 'all', 'news')}
    return {'projects': True, 'news': True}


if __name__ == '__main__':
    for key, value in mode(os.environ.get('EVENT_NAME'), os.environ.get('SCHEDULE'), os.environ.get('RUN_MODE')).items():
        print(key + '=' + str(value).lower())
