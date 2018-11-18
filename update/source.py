import binascii
import git


class Source:

    def __init__(self):
        pass

    @staticmethod
    def find(content, start_string, end_string):
        start_index = content.index(start_string)
        start_index += len(start_string)
        end_index = content.index(end_string, start_index)
        return start_index, end_index

    @staticmethod
    def find_string(path, start_string, end_string):
        with open(path) as f:
            content = f.read()
        start_index, end_index = Source.find(content, start_string, end_string)
        return content[start_index:end_index]

    @staticmethod
    def find_int(path, key):
        start_string = "." + key + " = "
        end_string = ","
        return int(Source.find_string(path, start_string, end_string))

    @staticmethod
    def find_data(path, start_string=".data = {", end_string="}"):
        c_data = Source.find_string(path, start_string, end_string)
        ascii_data = c_data.replace("0x", "").replace(", ", "")
        return binascii.unhexlify(ascii_data)

    @staticmethod
    def commit_data_string():
        repo = git.Repo(search_parent_directories=True)
        commit = bytearray(binascii.unhexlify(repo.head.object.hexsha))
        return ", ".join(("0x%0.2x" % value) for value in commit)

    @staticmethod
    def replace_commit(path):
        with open(path) as f:
            content = f.read()
        try:
            start_index, end_index = Source.find(content, ".data = {", "}")
        except ValueError:
            return
        content = content[:start_index] + Source.commit_data_string() + content[end_index:]
        with open(path, "w") as f:
            f.write(content)
