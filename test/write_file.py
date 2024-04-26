"""
unit tests without the ugliness of mocking

(mock tests have their place, but the overhead is awful)
"""
import os
from cabinet import Cabinet

def test_write_file():
    """
    test the write_file function
    """
    # Create a Cabinet instance
    cabinet = Cabinet()
    cabinet.path_log = "/tmp/cabinet/log"

    # Define test cases
    test_cases = [
        {
            "file_name": "testfile.txt",
            "path_file": "/tmp/cabinet/test",
            "content": "Hello, World!",
            "append": False,
            "is_quiet": True,
            "expected_result": True,
            "description": "Normal file creation"
        },
        {
            "file_name": "testfile.txt",
            "path_file": "/tmp/cabinet/test",
            "content": " More text",
            "append": True,
            "is_quiet": True,
            "expected_result": True,
            "description": "Appending to existing file"
        },
        {
            "file_name": "",
            "path_file": "/tmp/cabinet/test",
            "content": "Should fail",
            "append": False,
            "is_quiet": True,
            "expected_result": False,
            "description": "Testing with empty filename"
        }
    ]

    # Run test cases
    for case in test_cases:
        try:
            print(f"Testing: {case['description']}")
            result = cabinet.write_file(case["file_name"], case["path_file"],
                                        case["content"], case["append"], case["is_quiet"])
            # Check result and file content
            if result != case["expected_result"]:
                print(f"FAIL: {case['description']}")
                continue

            if result:  # If expected to succeed, check file content
                file_path = os.path.join(case["path_file"], case["file_name"])
                if not os.path.exists(file_path):
                    print(f"FAIL: {case['description']} - File does not exist")
                    continue
                with open(file_path, 'r', encoding='utf-8') as file:
                    file_content = file.read()
                    expected_content = case["content"]
                    if case["append"] and not file_content.endswith(expected_content):
                        print(f"FAIL: {case['description']} - Content not appended properly")
                        continue
                    elif not case["append"] and file_content != expected_content:
                        print(f"FAIL: {case['description']} - Content does not match")
                        continue
            print(f"PASS: {case['description']}")
        except Exception as e:
            print(f"FAIL: {case['description']} - Exception occurred: {str(e)}")

if __name__ == "__main__":
    test_write_file()
