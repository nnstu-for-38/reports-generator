import cache
import api
import codecs
import datetime
import time
import json
import pyquery

from jinja2 import Environment, FileSystemLoader, select_autoescape

HEADER = '<!DOCTYPE html><html>' \
         '<head><title>Отчёт о решении задач на codeforces</title>' \
         '<meta charset="UTF-8" />' \
         '<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.1.3/css/bootstrap.min.css" integrity="sha384-MCw98/SFnGE8fJT3GXwEOngsV7Zt27NXFoaoApmYm81iuXoPkFOJwJ8ERdknLPMO" crossorigin="anonymous">' \
         '<script src="https://code.jquery.com/jquery-3.3.1.slim.min.js" integrity="sha384-q8i/X+965DzO0rT7abK41JStQIAqVgRVzpbzo5smXKp4YfRvH+8abtTE1Pi6jizo" crossorigin="anonymous"></script>' \
         '<script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.3/umd/popper.min.js" integrity="sha384-ZMP7rVo3mIykV+2+9J3UJ46jBk0WLaUAdn689aCwoqbBJiSnjAK/l8WvCWPIPm49" crossorigin="anonymous"></script>' \
         '<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.1.3/js/bootstrap.min.js" integrity="sha384-ChfqqxuZUCnJSK3+MXmPNIyE6ZbWh2IMqE241rYiqJxyMiZ6OW/JmZQ5stwEULTy" crossorigin="anonymous"></script>' \
         '<style type="text/css">' \
         'body { padding-top: 50px; }' \
         '</style>' \
         '</head><body>'

now = datetime.datetime.now()

FOOTER = '<div class="container"><div class="row"><div class="col-md-12"><hr />' \
         '<p>Последнее обновление: {}' \
         '<p>Все вопросы, пожелания, найденные ошибки и неточности можно сообщить <a href="https://github.com/nnstu-for-38/nnstu-for-38.github.io/issues/new">создав issue</a>' \
         '<p>Generated by <a href="https://github.com/nnstu-for-38/reports-generator">python script</a>. Big thanks <a href="https://codeforces.com/">Codeforces</a> for the <a href="http://codeforces.com/api/help">API</a>' \
         '<p>Powered by <a href="https://pages.github.com/">Github Pages</a> and <a href="https://getbootstrap.com/">Bootstrap</a>' \
         '</div></div></div></body></html>'.format(now.strftime("%d.%m.%Y %H:%M"))


def next_date_timestamp(date):
    current = datetime.datetime.strptime(date.strftime("%d/%m/%Y"), "%d/%m/%Y")
    next = current + datetime.timedelta(days=1)
    return time.mktime(next.timetuple())


def datefilter(v, format='%d.%m.%Y'):
    return v.strftime(format)


def datetimefilter(v, format='%d.%m.%Y %H:%M'):
    return v.strftime(format)


def fetch_submission_source_code(submission):
    if submission['contestId'] == '100092':
        return None # skip trainings. source code cannot be obtained

    url = 'https://codeforces.com/contest/{}/submission/{}'.format(
        submission['contestId'], submission['id'])
    connected = False
    while not connected:
        try:
            d = pyquery.PyQuery(url)
            connected = True
        except TimeoutError:
            connected = False
            time.sleep(2)
        except OSError:
            connected = False
            time.sleep(2)

    html = d("#program-source-text").html()
    if html is None:
        print('cannot obtain program sources for: {}'.format(url))
        return None

    return html


def fetch_data(data_file):
    with open('data/{}'.format(data_file)) as file:
        data = json.load(file)

    # TODO: term must be configurable here (0 is hardcoded right now)
    d, m, y = data['terms'][0]['from']
    from_date = datetime.date(y, m, d)

    for handle in data['handles']:
        print('Processing "{}" handle'.format(handle))
        existing_submissions = cache.get('{}.submissions'.format(handle))
        if existing_submissions is None:
            existing_submissions = {}

        new_submissions = api.fetch_submissions(handle)
        # TODO: error handling

        for submission_id, submission in new_submissions.items():
            submission_id = str(submission_id)
            if submission_id not in existing_submissions:
                startTimestamp = time.mktime(from_date.timetuple())
                if submission['creationTimeSeconds'] >= startTimestamp:
                    print('trying to get source code for submission {}'.format(submission_id))
                    code = fetch_submission_source_code(submission)
                else:
                    code = None
                submission['source_code'] = code

                # add new submission into existing
                existing_submissions[submission_id] = submission
                time.sleep(3)

        cache.save('{}.submissions'.format(handle), existing_submissions)
        time.sleep(5)


def render_personal_report(handle, term_data):
    # Prepare data
    all_submissions = cache.get('{}.submissions'.format(handle))
    if all_submissions is None:
        print('Please fetch data first!')
        return

    all_submissions = all_submissions.values()

    data = sorted(all_submissions, key=lambda k: k['creationTimeSeconds'])

    submissions_per_problem = {}
    for submission in data:
        problem_index = str(submission['problem']['contestId']) + submission['problem']['index']
        if problem_index not in submissions_per_problem:
            submissions_per_problem[problem_index] = [submission]
        else:
            submissions_per_problem[problem_index].append(submission)

    homeworks_data = []
    included_into_homework = set()

    for homework in term_data['homeworks']:
        end_timestamp = next_date_timestamp(homework['to'])

        num_in_time = 0
        num_late = 0
        problems_data = {}
        for problem_index in homework['problems']:
            problems_data[problem_index] = {}

        for problem_index in homework['problems']:
            included_into_homework.add(problem_index)

            if problem_index not in submissions_per_problem:
                problems_data[problem_index]['no_submissions'] = True
            else:
                problems_data[problem_index]['no_submissions'] = False
                got_ac = False
                in_time = False
                for submission in submissions_per_problem[problem_index]:
                    if submission['verdict'] == 'OK':
                        got_ac = True
                        if submission['creationTimeSeconds'] < end_timestamp:
                            in_time = True
                            break
                problems_data[problem_index]['got_ac'] = got_ac
                problems_data[problem_index]['in_time'] = in_time
                problems_data[problem_index]['num_submissions'] = len(submissions_per_problem[problem_index])

                num_in_time = num_in_time + 1 if got_ac and in_time else num_in_time
                num_late = num_late + 1 if got_ac and not in_time else num_late

        homeworks_data.append({
            'info': homework,
            'per_problem_info': problems_data,
            'num_in_time': num_in_time,
            'num_late': num_late,
            'total_problems': len(homework['problems'])
        })

    classworks_data = []
    included_into_classwork = set()

    for classwork in term_data['classworks']:
        problems_data = {}
        for problem_index in classwork['problems']:
            problems_data[problem_index] = {}

        for problem_index in classwork['problems']:
            included_into_classwork.add(problem_index)

            if problem_index not in submissions_per_problem:
                problems_data[problem_index]['no_submissions'] = True
            else:
                problems_data[problem_index]['no_submissions'] = False

                got_ac = False
                for submission in submissions_per_problem[problem_index]:
                    if submission['verdict'] == 'OK':
                        got_ac = True
                        break

                problems_data[problem_index]['got_ac'] = got_ac

        classworks_data.append({
            'info': classwork,
            'per_problem_info': problems_data
        })

    additional_data = []

    startTimestamp = time.mktime(term_data['from'].timetuple())
    for problem_index, submissions in submissions_per_problem.items():
        if problem_index in included_into_homework or problem_index in included_into_classwork:
            continue

        actual_submissions = []
        for submission in submissions:
            if submission['creationTimeSeconds'] >= startTimestamp:
                actual_submissions.append(submission)

        if len(actual_submissions) == 0:
            continue

        got_ac = False
        for submission in actual_submissions:
            if submission['verdict'] == 'OK':
                got_ac = True

        additional_data.append({
            'problem_index': problem_index,
            'got_ac': got_ac
        })

    # Prepare template
    env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=select_autoescape('html')
    )
    env.filters['date'] = datefilter
    env.filters['datetime'] = datetimefilter

    template = env.get_template('individual.html')

    with codecs.open('reports/{}.html'.format(handle), 'w', "utf-8") as file:
        file.write(template.render(handle=handle,
                                   submissions=submissions_per_problem,
                                   homeworks=homeworks_data,
                                   classworks=classworks_data,
                                   last_update=datetime.datetime.now(),
                                   additional=additional_data))


def render_personal_reports(data_file):
    with open('data/{}'.format(data_file)) as file:
        data = json.load(file)
        for term in data['terms']:
            d, m, y = term['from']
            term['from'] = datetime.date(y, m, d)
            for homework in term['homeworks']:
                d, m, y = homework['from']
                homework['from'] = datetime.date(y, m, d)
                d, m, y = homework['to']
                homework['to'] = datetime.date(y, m, d)
            for classwork in term['classworks']:
                d, m, y = classwork['dates'][0]
                classwork['dates'][0] = datetime.date(y, m, d)
                d, m, y = classwork['dates'][1]
                classwork['dates'][1] = datetime.date(y, m, d)

        for handle in data['handles']:
            # TODO: term must be configurable
            render_personal_report(handle, data['terms'][0])


def render_main_page(data_file):
    # Prepare data
    with open('data/{}'.format(data_file)) as file:
        data = json.load(file)
        for term in data['terms']:
            d, m, y = term['from']
            term['from'] = datetime.date(y, m, d)
            for homework in term['homeworks']:
                d, m, y = homework['from']
                homework['from'] = datetime.date(y, m, d)
                d, m, y = homework['to']
                homework['to'] = datetime.date(y, m, d)
            for classwork in term['classworks']:
                d, m, y = classwork['dates'][0]
                classwork['dates'][0] = datetime.date(y, m, d)
                d, m, y = classwork['dates'][1]
                classwork['dates'][1] = datetime.date(y, m, d)

    # Prepare template
    env = Environment(
        loader=FileSystemLoader('templates'),
        autoescape=select_autoescape('html')
    )
    env.filters['date'] = datefilter
    env.filters['datetime'] = datetimefilter

    template = env.get_template('main-page.html')

    with codecs.open('reports/index.html', 'w', "utf-8") as file:
        # TODO: term must be configurable
        file.write(template.render(handles=data['handles'],
                                   homeworks=data['terms'][0]['homeworks'],
                                   classworks=data['terms'][0]['classworks'],
                                   last_update=datetime.datetime.now()))
