import argparse
import sys
from aas_test_tools import api, file


def run_file_test(argv):
    parser = argparse.ArgumentParser(description='Runs test cases')
    parser.add_argument('file',
                        type=argparse.FileType('r'),
                        help='the file to check')
    args = parser.parse_args(argv)
    result = file.check_aasx_file(args.file)
    print(result)


def run_api_test(argv):
    parser = argparse.ArgumentParser(description='Runs test cases')
    parser.add_argument('server',
                        type=str,
                        help='server to run the tests against')
    parser.add_argument('--dry',
                        action='store_true',
                        help="dry run, do not send requests")
    parser.add_argument('--profile',
                        type=str,
                        help='selected profile')
    args = parser.parse_args(argv)
    if args.profile:
        profiles = set([args.profile])
    else:
        profiles = None
    tests = api.generate_tests(profiles=profiles)
    api.execute_tests(tests, args.server, args.dry)


commands = {
    'file': run_file_test,
    'api': run_api_test,
}

if len(sys.argv) <= 1:
    print(f"Usage: {sys.argv[0]} COMMAND OPTIONS...")
    print("Available commands:")
    print("  file     Check a file for compliance.")
    print("  api      Check a server instance for compliance.")
    exit(1)

command = sys.argv[1]

if command not in commands:
    print(f"Unknown command '{command}', must be one of {', '.join(commands)}")
    exit(1)

remaining_args = sys.argv[2:]
commands[command](remaining_args)
