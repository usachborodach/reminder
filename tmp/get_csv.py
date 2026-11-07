import subprocess
import os

base_path = os.path.dirname(__file__)
os.chdir(base_path)

remote_csv_path = '/root/myfirstvps/utilities/reminder/reminders.csv'

command = ['scp', f'myfirstvps:{remote_csv_path}', base_path]
subprocess.run(command)