def get_csv_from_vps():
    command = ['scp', f'myfirstvps:{REMOTE_CSV_PATH}', LOCAL_CSV_PATH]
    subprocess.run(command)