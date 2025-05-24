import re

class MermaidParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.blocks = {}
        self.logic = []

    def parse(self):
        mermaid_comment = '%%'
        loop_pattern_single = re.compile(r'^subgraph\s*(\w+)\s*\[(.+)\]$')
        loop_pattern_begin = re.compile(r'^subgraph\s*(\w+)\s*\[(.*)$')
        block_pattern_begin = re.compile(r'^(\w+)\s*\[(.*)$')
        block_pattern_single = re.compile(r'^(\w+)\s*\[(.+)\]$')
        logic_pattern = re.compile(r'^(\w+)\s*-->\s*(\|\w+\|)?\s*(\w+)$')
        with open(self.file_path, 'r') as file:
            lines = file.readlines()

        current_block_id = None
        current_block_lines = []
        in_block = False
        in_loop = False

        for line in lines:
            line = line.strip()
            if self.ignore_comments(line):
                continue

            # Single-line block
            match = block_pattern_single.match(line)
            if match:
                block_id, content = match.groups()
                self.blocks[block_id] = content.strip()
                continue

            # Single-line loop block
            match = loop_pattern_single.match(line)
            if match:
                block_id, content = match.groups()
                current_block_id = block_id
                current_block_lines = [content]
                in_loop = True
                continue

            # Start Loop block
            if not in_loop:
                start_match = loop_pattern_begin.match(line)
                if start_match and not line.endswith(']'):
                    current_block_id, first_line = start_match.groups()
                    current_block_lines = [first_line]
                    in_loop = True
                    in_block = True
                    continue

            # Multiline loop block continuation
            if in_loop and in_block:
                if line.endswith(']'):
                    current_block_lines.append(line[:-1])
                    self.blocks[current_block_id] = "\n".join(current_block_lines).strip()
                    in_block = False
                else:
                    current_block_lines.append(line)
                continue

            # Loop block contents
            if in_loop:
                if line.startswith('end'):
                    current_block_lines.append(line[:-1])
                    self.blocks[current_block_id] = "\n".join(current_block_lines).strip()
                    in_loop = False
                else:
                    current_block_lines.append(line)
                continue


            # Start of a multiline block
            if not in_block:
                start_match = block_pattern_begin.match(line)
                if start_match and not line.endswith(']'):
                    current_block_id, first_line = start_match.groups()
                    current_block_lines = [first_line]
                    in_block = True
                    continue

            # Multiline continuation
            if in_block:
                if line.endswith(']'):
                    current_block_lines.append(line[:-1])
                    self.blocks[current_block_id] = "\n".join(current_block_lines).strip()
                    in_block = False
                else:
                    current_block_lines.append(line)
                continue

            # Logic connections
            logic_match = logic_pattern.match(line)
            if logic_match:
                if logic_match.lastindex == 3:
                    self.logic.append((logic_match.group(1),
                        logic_match.group(3),logic_match.group(2)))
                else:
                    self.logic.append((logic_match.group(1), logic_match.group(2)))

    def ignore_comments(self, line):
        mermaid_comment = '%%'
        if not line or line.startswith("flowchart") or \
        line.startswith(mermaid_comment):
            print(line)
            return True
        else:
            return False

    def get_blocks(self):
        return self.blocks

    def get_logic(self):
        return self.logic

class ControlBlock(MermaidParser):
    def __init__(self):
        pass
