import configargparse
import re
import warnings

from math import ceil

freq_multiplier_units = {'mhz' : 1000000,
                         'khz' : 1000,
                         'hz'  : 1}

time_multiplier_units = {'ms' : 1000000,
                         'us' : 1000,
                         'ns' : 1}

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

        self.current_block_id = None
        self.current_block_lines = []
        in_block = False
        in_loop = False

        for line in lines:
            line = line.strip()
            if self.ignore_comments(line):
                continue

            if self.get_single_line_block(line):
                continue

            # Single-line loop block
            if self.get_single_loop_block(line):
                in_loop = True
                continue

            # Start Loop block
            if not in_loop:
                if self.start_loop_block(line):
                    in_loop = True
                    in_block = True
                    continue

            # Multiline loop block continuation
            if in_loop and in_block:
                if self.end_of_line(line):
                    self.block_join(line)
                    in_block = False
                else:
                    self.block_append(line)
                continue

            # Loop block contents
            if in_loop:
                if self.end_of_loop(line):
                    self.block_join(line)
                    in_loop = False
                else:
                    self.block_append(line)
                continue


            # Start of a multiline block
            if not in_block:
                if self.start_multi_block(line):
                    in_block = True
                    continue

            # Multiline continuation
            if in_block:
                if self.end_of_line(line):
                    self.block_join(line)
                    in_block = False
                else:
                    self.block_append(line)
                continue

            # Logic connections
            self.match_logic(line)

    def start_loop_block(self, line):
        """
        """
        loop_pattern_begin = re.compile(r'^subgraph\s*(\w+)\s*\[(.*)$')
        return self.match_block(line, loop_pattern_begin)

    def start_multi_block(self, line):
        """
        """
        block_pattern_begin = re.compile(r'^(\w+)\s*\[(.*)$')
        return self.match_block(line, block_pattern_begin)

    def match_block(self, line, pattern):
        """
        """
        start_match = pattern.match(line)
        if start_match and not line.endswith(']'):
            self.current_block_id, first_line = start_match.groups()
            self.current_block_lines = [first_line]
            return True

    def end_of_loop(self, line):
        """
        """
        if line.startswith('end'):
            return True
        else:
            return False

    def get_single_loop_block(self, line):
        loop_pattern_single = re.compile(r'^subgraph\s*(\w+)\s*\[(.+)\]$')
        match = loop_pattern_single.match(line)
        if match:
            block_id, content = match.groups()
            self.current_block_id = block_id
            self.current_block_lines = [content]
            return True

    def end_of_line(self, line):
        """
           Checks for end of line
        """
        if line.endswith(']'):
            return True
        else:
            return False

    def block_join(self, line):
        """
        """
        self.current_block_lines.append(line[:-1])
        self.blocks[self.current_block_id] = "\n".join(self.current_block_lines).strip()
        return

    def block_append(self, line):
        self.current_block_lines.append(line)
        return

    def match_logic(self, line):
        """
            Parses line to get any logic information 
            e.g:
            key1 --> key2
            key1 --> |key3| key2
        """
        logic_pattern = re.compile(r'^(\w+)\s*-->\s*(\|\w+\|)?\s*(\w+)$')
        logic_match = logic_pattern.match(line)
        if logic_match:
            if logic_match.lastindex == 3: # Has 3 information
                self.logic.append((logic_match.group(1),
                    logic_match.group(3),logic_match.group(2)))
            else:
                self.logic.append((logic_match.group(1), logic_match.group(2)))

    def ignore_comments(self, line):
        """
            Parses line and remove comments, empty line or flowchart keyword
        """
        mermaid_comment = '%%'
        if not line or line.startswith("flowchart") or \
        line.startswith(mermaid_comment):
            return True
        else:
            return False

    def get_single_line_block(self, line):
        """  Parses line  and looks for single line block
            block_id [ content ]
        """
        block_pattern_single = re.compile(r'^(\w+)\s*\[(.+)\]$')
        match = block_pattern_single.match(line)
        if match:
            block_id, content = match.groups()
            self.blocks[block_id] = content.strip()
            return True
        else:
            return False

    def get_blocks(self):
        return self.blocks

    def get_logic(self):
        return self.logic

class Block(MermaidParser):
    def __init__(self, block_id, content):
        self.block_id = block_id
        self.content = content
        self.first_row = None
        self.last_row = None
        self.written = False

    def split_comments(self,line):
        text = line.split("#",1)
        if len(text)>1:
            line = text[0]
            comment = "#" + text[1]
        else:
            line = text[0]
            comment = ""
        return line, comment

    def get_cols(self, line):
        line, comment = self.split_comments(line)
        delimiter = ",| |\t"
        line = line.lower()
        cols = list(filter(None, re.split(delimiter,line)))
        if comment:
            cols.append(comment)
        return cols

    def chan_on(self, chan_string):
        chan_list = []
        for part in self.get_cols(chan_string):
            if '-' in part:
                start, end = map(int, part.split('-'))
                chan_list.extend(range(start, end + 1))
            else:
                chan_list.append(int(part))
        return list(set(chan_list)) # remove duplicate

    def dac_update(self, dac_string):
        dac_list = []
        dac_value = []
        for part in self.get_cols(dac_string):
            ch, val = part.split(":")
            dac_list.append(int(ch))
            dac_value.append(float(val))
        return dict(zip(dac_list, dac_value))

    def split_unit(self, string):
        return re.findall(r'\d+|\D+', string)

    def parse_contents(self):
        return self.content.split('\n')

    def is_comment(self, line):
        if line.strip().startswith("#"):
            return True
        else:
            return False

    def eat_space_between_units(self, l):
        t = [x in time_multiplier_units for x in l]
        f = [x in freq_multiplier_units for x in l]
        for i, x in enumerate(t):
            if x:
                l[i-1] += l[i]
                l.pop(i)

        for i, x in enumerate(f):
            if x:
                l[i-1] += l[i]
                l.pop(i)

        return l

    def get_dac(self, cols):
        assert cols[0].lower() == 'dac', "Keyword missing"
        line = ','.join(cols[1:])
        line, comments = self.split_comments(line)
        cols = []
        return self.dac_update(line), comments, cols 

    def get_chan(self, cols):
        assert cols[0].lower() == 'chan', "Keyword missing"
        try:
            dac_idx = cols.index('dac')
            line = ','.join(cols[1:dac_idx])
            comments = ''
            cols = cols[dac_idx:]
        except ValueError:
            line = ','.join(cols[1:]) # without dac,
            cols = []
        line, comments = self.split_comments(line)
        return self.chan_on(line), comments, cols

    def set_exinput(self, line):
        '''
            Get the external input channel used. Must be e1,e2,e3 or e4.
            Returns 1,2,3 or 4.
        '''
        part = line[0]
        assert part in ['e1', 'e2', 'e3', 'e4']
        self.external_input = int(part[1:])


class ControlBlock(Block):
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "control"
        self.auxconfig = 0
        self.start_address = 0 # Default to 0
        self.ivars = [0, 0, 0, 0] # Default to 0
        self.evars = [0, 0, 0, 0] # Default to 0
        self.auxline_pol = 0 # Set to NIM by default
        self.clock_select = 0 # auto by default
        self.level = 0 # Set to NIM by default
        self.dacconfig = 0 # Set to static by default
        self.patgen_128bit = False # Set to 64bit version by default
        self.dacs = [0,0,0,0,0,0,0,0]
        self.inthreshold = 59000 # Nim by default


        self.auxselect = {'normal': 0, 'delayed':1, 'main':2,'ref':3}
        self.clockselect = {'auto': 0, 'external':1, 'internal':2,'direct':3}
        self.dacselect = {'static': 0, 'single':1, 'half':2,'full':3}
        self.control_grammar = ["clock", "evars", "ivars", "auxout",
                "dacconfig", "version", "inlevel", "auxconfig",
                "startaddress", "dacstatic"]

    def process_control(self):
        for line in self.parse_contents():
            cols = self.get_cols(line)
            first_col = cols[0]
            next_cols = cols[1:]
            assert first_col in self.control_grammar, f"{first_col} doesn't match syntax"
            """ # To migrate to python3.10 syntax
            match first_col:
                case "clock":
                    ...
                case "evars":
                    ...
            """
            if first_col == self.control_grammar[0]:
                self.set_clock(next_cols)
            elif first_col == self.control_grammar[1]:
                self.set_evars(next_cols)
            elif first_col == self.control_grammar[2]:
                self.set_ivars(next_cols)
            elif first_col == self.control_grammar[3]:
                self.set_auxline_polarity(next_cols)
            elif first_col == self.control_grammar[4]:
                self.set_DACconfig(next_cols)
            elif first_col == self.control_grammar[5]:
                self.set_patgenversion(next_cols)
            elif first_col == self.control_grammar[6]:
                self.set_external_input_polarity(next_cols)
            elif first_col == self.control_grammar[7]:
                self.set_auxconfig(next_cols)
            elif first_col == self.control_grammar[8]:
                self.set_startaddress(next_cols)
            elif first_col == self.control_grammar[9]:
                self.set_staticDAC(next_cols)

    def set_clock(self, clock_cols):
        clock_cols = self.eat_space_between_units(clock_cols)
        for i, part in enumerate(clock_cols):
            if i == 0: # Clock value and unit
                value, unit = self.split_unit(part)
                assert unit in freq_multiplier_units.keys(), "Undefined frequency units.(Hz,Khz,MHz)"
                try:
                    clock = int(value)
                except ValueError as emsg:
                    raise Exception("Clock value should be integer, change units if necessary")
                self.clock = clock * freq_multiplier_units.get(unit) #Hz
                assert self.clock <= 100000000, "Clock frequency too large"
                self.timestep = int(1e9/self.clock) #ns
        if i == 1: # Clock select
            assert part in self.clockselect.keys(), "Undefined clock select"
            self.clock_select = self.clockselect.get(part)
        else:
            self.clock_select = 0 # auto by default
        if self.clock_select != 3:
            assert self.clock == 100_000_000, "Clock select and clock freq don't agree"

    def set_evars(self, evars_cols):
        assert len(evars_cols) <= 4, "Too many external vars"
        for i, val in enumerate(evars_cols):
            val = int(val)
            assert val < 65536, "External variable overflow"
            self.evars[i] = val

    def set_ivars(self, ivars_cols):
        assert len(ivars_cols) <= 4, "Too many internal vars"
        for i, val in enumerate(ivars_cols):
            val = int(val)
            assert val < 65536, "Internal variable overflow"
            self.ivars[i] = val

    def set_auxconfig(self, aux_cols):
        part = aux_cols[0]
        assert part in self.auxselect.keys(), "Undefined auxline select"
        self.auxconfig = self.auxselect.get(part)

    def set_startaddress(self, aux_cols):
        part = int(aux_cols[0])
        assert part < 512, "Undefined auxline select"
        self.start_address = part


    def set_auxline_polarity(self, aux_cols):
        part = aux_cols[0]
        assert part in ['0', '1', 'nim' ,'ttl'], "Undefined auxout"
        if part in ['0', 'nim']:
            self.auxline_pol = 0
        elif part in ['1', 'ttl']:
            self.auxline_pol = 1

    def set_external_input_polarity(self, aux_cols):
        part = aux_cols[0]
        assert part in ['0', '1', 'nim' ,'ttl'], "Undefined auxout"
        if part in ['0', 'nim']:
            self.level = 0
        elif part in ['1', 'ttl']:
            self.level = 1


    def set_DACconfig(self, dac_config_cols):
        part = dac_config_cols[0]
        assert part in self.dacselect.keys(), f"Undefined DAC config"
        self.dacconfig = self.dacselect.get(part)

    def set_staticDAC(self, dac_vals):
        line = ','.join(dac_vals)
        dac_dict = self.dac_update(line)
        for dac_chan, val in dac_dict.items():
            self.dacs[dac_chan] = val

    def set_patgenversion(self, patgen_ver_cols):
        part = patgen_ver_cols[0]
        assert part in ['128bit', '64bit']
        if part == '128bit':
            self.patgen_128bit = True
        elif part == '64bit':
            self.patgen_128bit = False

    def process(self):
        self.process_control()

class SeqBlock(Block):
    """
    Sequence block holds the sequence of steps to go through in a list of dict.
    The keys of the dict are time(in ns), chan, use_ivar, [dac], comments.
    Sequences has not much grammar involved.
    """
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "sequence"
        self.last_step_is_loop = False
        self.sequence_name = ""
        self.sequence = []

    def process_seq(self):
        for i, line in enumerate(self.parse_contents()):
            if i == 0 and self.is_comment(line):
                self.sequence_name  = line[1:]
                continue
            cols = self.get_cols(line)
            self.add_seq_from_cols(cols)

    def add_seq_from_cols(self, cols):
        time, cols = self.get_time(cols)
        use_ivar, cols = self.get_ivar(cols)
        chan, comments1, cols = self.get_chan(cols)
        if cols:
            dac, comments2, cols = self.get_dac(cols)
        else:
            dac = {}
            comments2 = ""
        self.sequence.append({'time' : time,
                              'chan' : chan,
                              'use_ivar' : use_ivar,
                              'dac' : dac,
                              'comments' : comments1 + comments2,
                              })

    def get_time(self, cols):
        try:
            value, unit = self.split_unit(cols[0])
            cols.pop(0)
        except ValueError:
            value = cols[0]
            unit = cols[1]
            cols.pop(0)
            cols.pop(0)
        finally:
            assert unit in time_multiplier_units.keys(), "Undefined time units. ns, us, ms)"
            time = int(value) * time_multiplier_units.get(unit) #ns
        return time , cols

    def get_ivar(self, cols):
        '''
            Get the internal variable index used for looping to increase time.
            ivar goes from 0--3
        '''
        try:
            index = cols.index('use_ivar')
            ivar = int(cols[index+1])
            cols.pop(index)
            cols.pop(index)
        except ValueError:
            ivar = None
        assert ivar in [None, 0, 1, 2, 3]
        return ivar, cols

    def process(self):
        self.process_seq()

class TriggerBlock(Block):
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "trigger"
        self.comment = []
        self.chan = []
        self.dac = []
        self.rate_defined = None
        self.count_defined = None
        self.trigger_grammar = ["extinput", "chan", "rate",
                "count", "success", "failure", "dac"]

    def process_trigger(self):
        for i, line in enumerate(self.parse_contents()):
            if self.is_comment(line) and i == 0:
                self.trigger_name = line[1:]
                continue
            cols = self.get_cols(line)
            first_col = cols[0]
            next_cols = cols[1:]
            if self.is_comment(next_cols[-1]):
                self.comment.append(next_cols[-1])
            assert first_col in self.trigger_grammar, f"{first_col} doesn't match syntax"
            if first_col == self.trigger_grammar[0]:
                self.set_exinput(next_cols)
            elif first_col == self.trigger_grammar[1]:
                self.set_chan(next_cols)
            elif first_col == self.trigger_grammar[2]:
                self.set_rate(next_cols)
            elif first_col == self.trigger_grammar[3]:
                self.set_count(next_cols)
            elif first_col == self.trigger_grammar[4]:
                self.set_success(next_cols)
            elif first_col == self.trigger_grammar[5]:
                self.set_failure(next_cols)
            elif first_col == self.trigger_grammar[6]:
                self.set_dac(next_cols)

    def set_chan(self, line):
        self.chan = self.chan_on(','.join(line))

    def set_rate(self, line):
        line = self.eat_space_between_units(line)
        for i, part in enumerate(line):
            if i == 0: # Clock value and unit
                value, unit = self.split_unit(part)
                assert unit in freq_multiplier_units.keys(), "Undefined frequency units.(Hz,Khz,MHz)"
                try:
                    rate = int(value)
                except ValueError as emsg:
                    raise Exception("Clock value should be integer, change units if necessary")
                self.rate = rate * freq_multiplier_units.get(unit) #Hz
        if self.rate_defined == None and self.count_defined == None:
            self.rate_defined = True
        else:
            raise Exception("Use only RATE or COUNT, not both")

    def set_count(self, line):
        line = self.eat_space_between_units(line)
        for i, part in enumerate(line):
            if i == 0:
                try:
                    self.count = int(part)
                except ValueError as emsg:
                    raise Exception("Count value should be integer, change units if necessary")
            elif i == 1:
                assert part == "in"
            elif i == 2:
                value, unit = self.split_unit(part)
                try:
                    time_span = int(value)
                except ValueError as emsg:
                    raise Exception("Time span should be integer, change units if necessary")
                assert unit in time_multiplier_units.keys(), "Undefined time units. ns, us, ms)"
                self.time_span = time_span * time_multiplier_units.get(unit) #ns

        if self.rate_defined == None and self.count_defined == None:
            self.count_defined = True
        else:
            raise Exception("Use only RATE or COUNT, not both")


    def set_success(self, outcome):
        self.success = outcome[0]

    def set_failure(self, outcome):
        self.failure = outcome[0]

    def check_consistent(self, success = None, failure = None):
        if success is not None:
            assert success == self.success, "Success logic doesn't match Block"
        if failure is not None:
            assert failure == self.failure, "Failure logic doesn't match Block"
        return

    def set_dac(self, line):
        pass

    def process(self):
        self.process_trigger()

class LoopBlock(Block):
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "loop"
        self.logic = []
        self.loop_logic = [] # List of list similar to parser.logic

    def process_loop(self):
        for i, line in enumerate(self.parse_contents()):
            if i == 0 and self.is_comment(line):
                self.loop_name  = line[1:]
                continue
            if i == 1:
                cols = self.get_cols(line)
                self.counter_var, self.counter_val,cols = self.get_ivar(cols)
                chan, comments1, cols = self.get_chan(cols)
                if cols:
                    dac, comments2, cols = self.get_dac(cols)
                else:
                    dac = {}
                    comments2 = ""
                self.loop_set={'chan' : chan,
                              'use_ivar' : self.counter_var,
                              'dac' : dac,
                              'comments' : comments1 + comments2,
                              }
            else:
                self.add_logic_from_line(line)

    def add_logic_from_line(self, line):
        self.match_logic(line)
        if len(self.logic)>0:
            self.loop_logic.append(self.logic.pop())

    def get_ivar(self, cols):
        '''
            Get the internal variable index used for looping.
            ivar goes from 0--3
        '''
        assert cols[0].lower() == 'ivar', "Wrong keyword"
        ivar = int(cols[1])
        assert ivar in [0, 1, 2, 3], "Counter index must be 0,1,2 or 3"
        val = int(cols[2])
        assert (val > 0 and val < 65536), "Counter value out of bounds"
        try:
            chan_idx = cols.index('chan')
            line = ','.join(cols[1:chan_idx])
            comments = ''
            cols = cols[chan_idx:]
        except ValueError:
            line = ','.join(cols[1:]) # without chan,
            cols = []
        line, comments = self.split_comments(line)
        return ivar, val, cols

    def process(self):
        self.process_loop()

class BranchBlock(Block):
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "branch"
        self.chan = []
        self.dac = []
        self.branch_grammar = ["extinput", "high", "low", "chan", "dac"]
    def process_branch(self):
        for i, line in enumerate(self.parse_contents()):
            if self.is_comment(line) and i == 0:
                self.branch_name = line[1:]
                continue
            cols = self.get_cols(line)
            if len(cols)>1:
                first_col = cols[0]
                next_cols = cols[1:]
                if self.is_comment(next_cols[-1]):
                    self.comment.append(next_cols[-1])
                assert first_col in self.branch_grammar, f"{first_col} doesn't match syntax"
                if first_col == self.branch_grammar[0]:
                    self.set_exinput(next_cols)
                elif first_col == self.branch_grammar[1]:
                    self.set_high(next_cols)
                elif first_col == self.branch_grammar[2]:
                    self.set_low(next_cols)
                elif first_col == self.branch_grammar[3]:
                    self.get_chan(next_cols)
                elif first_col == self.branch_grammar[4]:
                    self.get_dac(next_cols)
                else:
                    self.get_time(cols)
            else:
                self.get_time(cols)
        pass
    def get_time(self, cols):
        try:
            value, unit = self.split_unit(cols[0])
            cols.pop(0)
        except ValueError:
            value = cols[0]
            unit = cols[1]
            cols.pop(0)
            cols.pop(0)
        finally:
            assert unit in time_multiplier_units.keys(), "Undefined time units. ns, us, ms)"
            time = int(value) * time_multiplier_units.get(unit) #ns
        self.timestep = time

    def set_high(self, outcome):
        self.high = outcome[0]

    def set_low(self, outcome):
        self.low = outcome[0]

    def check_consistent(self, high = None, low = None):
        if high is not None:
            assert high == self.high, "High logic doesn't match Block"
        if low is not None:
            assert low == self.low, "Low logic doesn't match Block"
        return

    def process(self):
        self.process_branch()
    pass

def label_blocks(key):
    key = key.lower()
    if key.startswith("control"):
        return ControlBlock
    elif key.startswith("seq"):
        return SeqBlock
    elif key.startswith("trigger"):
        return TriggerBlock
    elif key.startswith("loop"):
        return LoopBlock
    elif key.startswith("branch"):
        return BranchBlock
    else:
        raise NotImplementedError(f"{key} not implemented.")

class Translator:
    def __init__(self, blocks, logic, filein, fileout, hex=True):
        self.blocks = {}
        self.hex = hex
        self.logic = logic
        self.config_bits = 0
        self.param_register = []
        self.new_dpatt_str = ""
        self.dpatt_str = f"#This file was generated by gen3.py using {filein}\n\n"
        self.fileout = fileout
        for key, value in blocks.items():
            cla = label_blocks(key)
            self.blocks[key] = cla(key,value)
            self.blocks[key].process()

        PARAMETERWRITE = 8; ADDRESSRESET=4; TABLERESET=1;
        self.process_config()
        self.write_config(PARAMETERWRITE+ADDRESSRESET+TABLERESET)
        self.write_param()
        self.preprocess_blocks()
        self.process_logic()
        self.write_out()

    def write_out(self):
        with open(self.fileout, 'w') as f:
            f.write(self.dpatt_str)
            f.write(self.new_dpatt_str)

    def preprocess_blocks(self):
        # Go through blocks and determine rows needed
        for block in self.blocks.values():
            if block.block_type == 'control':
                continue
            else:
                self.determine_num_rows(block)
        # Go through logic and deterimne start address and end address of each
        # block
        first = True
        count = 0
        for block, block_end, condition in self.logic:
            block = self.blocks[block]
            if first:
                block.first_row = 0
                count = block.first_row + block.num_rows
                block.last_row = count - 1
                first = False
                continue
            if block.first_row == None: # Need this since 0 is treated as False
                block.first_row = count
                count = block.first_row + block.num_rows
                block.last_row = count - 1
            if block.last_row == None:
                count = block.first_row + block.num_rows
                block.last_row = count - 1
            block_end = self.blocks[block_end]
            if block_end.first_row == None:
                block_end.first_row = count
                if block_end.block_type == 'loop':
                    count += 2 # 2 for loop load var and decrement counter
                    for block_loop, block_loop_end, condition_loop in \
                    block_end.loop_logic: # assume no nested loop
                        #print(block_loop, block_loop_end, condition_loop, count)
                        block_loop = self.blocks[block_loop]
                        if block_loop.first_row == None:
                            block_loop.first_row = count
                            count = block_loop.first_row + block_loop.num_rows
                            block_loop.last_row = count - 1
                        if block_loop.last_row == None:
                            count = block_loop.first_row + block_loop.num_rows
                            block_loop.last_row = count - 1
                        #print(block_loop.block_id, block_loop_end, condition_loop, count)
                if block_end.block_type == 'loop':
                    count += 2 # 2 for check and zero conndition address
                    block_end.last_row = count - 1
                else:
                    count += block_end.num_rows
                    block_end.last_row = count - 1

    def determine_num_rows(self, block):
        if block.block_type == 'sequence':
            self.preprocess_seq(block)
        elif block.block_type == 'trigger':
            self.preprocess_trigger(block)
        elif block.block_type == 'loop':
            self.preprocess_loop(block)
        elif block.block_type == 'branch':
            self.preprocess_branch(block)
        else:
            assert "Unknown block type"

    def preprocess_branch(self, block):
        '''
            Branching can either use 1 or 2 rows.
            It depends on the block of the "low" branch.
            1) Check condition with high address
            (2) Low address if not the next row 
        '''
        low = block.low
        name = block.block_id
        for i, l in enumerate(self.logic):
            if l[0] == name and self.logic[i+1][0] == low:
                block.num_rows = 1
                break
            else:
                block.num_rows = 2

    def preprocess_trigger(self, block):
        '''
            Reserve maximum 5 rows for external trigger.
            If ivar ( < 65us time_span) not needed steps 2 and 3 can be squashed
            1) Load evar (and ivar if needed)
            2) Decrement ivar counter
            3) Check non-zero ivar with address
            4) Check non-zero evar with address
            5) evar zero address condition
        '''
        block.num_rows = 5

    def preprocess_loop(self, block):
        '''
            Reserve 4 rows for internal loops.
            1) Load ivar
            2) Decrement ivar counter
            3) Check non-zero with address
            4) ivar zero address condition
        '''
        block.num_rows = 4

    def preprocess_seq(self, block):
        rows = 0
        seq_len = len(block.sequence)-1
        for j, step in enumerate(block.sequence):
            time = step['time']
            i = step['use_ivar']
            ivar = self.ivars[i] if i else None
            if ivar:
                rows += 1 # For load
                if time/self.maxtimestep/ivar/2 <= 1:
                    rows += 2 # For decrement and check
                else: # Happens at >85.8 s with max ivar(65535)
                    rows += 2 + \
                    ceil(time/self.maxtimestep/ivar)# Additional line gives 43s
                if j == seq_len:
                    rows += 1 # Add one more line if loop is last of sequence
                    block.last_step_is_loop = True
            elif ceil(time/self.maxtimestep)<1:
                rows += 1 # For single step
            else:
                additional_rows = ceil(time/self.maxtimestep)
                if additional_rows >4:
                    warnings.warn(f"This time step uses {additional_rows} " + \
                            "rows of the pattern. Consider using ivar")
                rows += additional_rows # For steps without loops.
        block.num_rows = rows

    def process_logic(self):
        self.new_dpatt_str += "\nholdaddr; ramprog;\n"
        self.pattern_row = 0
        for block_start, block_end, condition in self.logic:
            start = self.blocks[block_start]
            end = self.blocks[block_end]
            if start.written:
                continue
            if start.block_type == 'trigger':
                #print(f"start {start.block_id}, end {end.block_id}, condition" +
                #f" {condition}")
                self.process_trigger_logic(start, end, condition)
            if start.block_type == 'sequence':
                self.process_seq_logic(start, end)
            if start.block_type == 'loop':
                self.process_loop_logic(start, end)
            if start.block_type == 'branch':
                self.process_branch_logic(start, end, condition)

    def process_branch_logic(self, branch_block, end, condition):
        count = 0
        ext_chan = branch_block.external_input
        dig_chan = branch_block.chan
        timestep = branch_block.timestep
        comment = ''
        special_bcheck_address_high = self.blocks[branch_block.high].first_row
        special_bcheck_address_low = self.blocks[branch_block.low].first_row
        special_bcheck = ((ext_chan+3)<<12)
        self.new_dpatt_str += 'writew ' + \
                self.dig_chan_write(dig_chan) + \
                self.time_write(timestep) + \
                self.address_write(
                        address = special_bcheck_address_high,
                        special = special_bcheck,
                        cond = None,
                        ) + \
                self.row_num_write(comment=comment) + \
                '\n'
        count +=1
        if branch_block.num_rows == 2:
            self.new_dpatt_str += 'writew ' + \
                self.dig_chan_write(dig_chan) + \
                self.time_write(timestep) + \
                self.address_write(
                        address = special_bcheck_address_low,
                        special = None,
                        cond = None,
                        ) + \
                self.row_num_write(comment=comment) + \
                '\n'
            count +=1
        branch_block.written = True
        #print("branch", count, num_rows)

    def process_loop_logic(self, loop_block, loop_end):
        count = 0
        self.new_dpatt_str += "\n#" + loop_block.block_id + "  " + \
                              loop_block.loop_name + "\n"

        ivar_chan = loop_block.counter_var
        dig_chan = loop_block.loop_set['chan']
        load_timestep = self.timestep
        timestep = self.timestep
        comment  =loop_block.loop_set['comments']

        special_load = (1<<12) + ((2**ivar_chan)<<4)
        special_dec = (1<<12) + ((2**ivar_chan)<<8)
        special_icheck = ((12 + ivar_chan)<<12)
        icheck_row = loop_block.last_row - 1
        ivar = loop_block.counter_val

        self.new_dpatt_str += 'writew ' + \
                self.dig_chan_write(dig_chan) + \
                self.time_write(load_timestep) + \
                self.address_write(
                        address = None,
                        special = special_load,
                        cond = None,
                        ) + \
                self.row_num_write(comment= \
                    f"Load internal counter {ivar_chan} " + \
                    comment
                    ) + \
                '\n'
        repeat_icheck_address = self.pattern_row
        self.new_dpatt_str += 'writew ' + \
                self.dig_chan_write(dig_chan) + \
                self.time_write(timestep) + \
                self.address_write(
                        address = None,
                        special = special_dec,
                        cond = None,
                        ) + \
                self.row_num_write(comment=comment) + \
                '\n'
        count += 2
        for block_start, block_end, condition in loop_block.loop_logic:
            start = self.blocks[block_start]
            if block_end == 'loop_check':
                end.block_id = 'loop_check'
                end.loop_check_row = icheck_row
            else:
                end = self.blocks[block_end]
            if start.written:
                continue
            if start.block_type == 'trigger':
                #print(f"start {start.block_id}, end {end.block_id}, condition" +
                #f" {condition}")
                self.process_trigger_logic(start, end, condition)
            if start.block_type == 'sequence':
                self.process_seq_logic(start, end)

        self.new_dpatt_str += 'writew ' + \
                self.dig_chan_write(dig_chan) + \
                self.time_write(timestep) + \
                self.address_write(
                        address = repeat_icheck_address,
                        special = special_icheck,
                        cond = None,
                        ) + \
                self.row_num_write(comment=comment) + \
                '\n'
        address = loop_end.first_row
        self.new_dpatt_str += 'writew ' + \
                self.dig_chan_write(dig_chan) + \
                self.time_write(timestep) + \
                self.address_write(
                        address = address,
                        special = None,
                        cond = None,
                        ) + \
                self.row_num_write(comment=comment) + \
                '\n'
        count += 2
        #print("loop", count, loop_block.num_rows)

    def process_seq_logic(self, start, end):
        count = 0
        seq_len = len(start.sequence) - 1
        self.new_dpatt_str += "\n#" + start.block_id + "  " + \
                              start.sequence_name + "\n"
        for j, step in enumerate(start.sequence):
            time = step['time']
            ivar_chan = step['use_ivar']
            dig_chan = step['chan']
            comment = step['comments']
            ivar = self.ivars[ivar_chan] if ivar_chan else None
            if ivar:
                if start.last_step_is_loop and j == seq_len:
                    time -= time - self.timestep # reserve 1 timestep to point
                                                 # to next address if last loop
                                                 # in sequence block
                special_load = (1<<12) + ((2**ivar_chan)<<4)
                special_dec = (1<<12) + ((2**ivar_chan)<<8)
                special_icheck = ((12 + ivar_chan)<<12)
                if time/self.maxtimestep/ivar/2 <= 1:
                    time_loop, load_timestep= self.timebalancer(time, ivar, 2)
                    self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(load_timestep) + \
                            self.address_write(
                                    address = None,
                                    special = special_load,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment= \
                                f"Load internal counter {ivar_chan} " + \
                                comment
                                              ) + \
                            '\n'
                    repeat_icheck_address = self.pattern_row
                    self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(time_loop) + \
                            self.address_write(
                                    address = None,
                                    special = special_dec,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment=comment) + \
                            '\n'

                    self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(time_loop) + \
                            self.address_write(
                                    address = repeat_icheck_address,
                                    special = special_icheck,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment=comment) + \
                            '\n'
                    count += 3 # For load, decrement and check
                else: # Happens at >84.8 s with max ivar(65535)
                    lines = ceil(time/self.maxtimestep/ivar)
                    time_loop, load_timestep= self.timebalancer(time, ivar,
                            lines)
                    self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(load_timestep) + \
                            self.address_write(
                                    address = None,
                                    special = special_load,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment= \
                                f"Load internal counter {ivar_chan} " + \
                                comment
                                              ) + \
                            '\n'
                    repeat_icheck_address = self.pattern_row
                    self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(time_loop) + \
                            self.address_write(
                                    address = None,
                                    special = special_dec,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment=comment) + \
                            '\n'

                    for ii in range(lines-2): # minus decrement and check
                        self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(time_loop) + \
                            self.address_write(
                                    address = None,
                                    special = None,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment=comment) + \
                            '\n'
                    self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(time_loop) + \
                            self.address_write(
                                    address = repeat_icheck_address,
                                    special = special_icheck,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment=comment) + \
                            '\n'
                    count += 1 + \
                        ceil(time/self.maxtimestep/ivar)
                if start.last_step_is_loop and j == seq_len: # if last loop
                    self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(out.timestep) + \
                            self.address_write(
                                    address = end.first_row,
                                    special = None,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment=comment) + \
                            '\n'
                    count += 1
            elif ceil(time/self.maxtimestep)<1:
                address = end.first_row if j == seq_len else None
                self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(time) + \
                            self.address_write(
                                    address = address,
                                    special = None,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment=comment) + \
                            '\n'
                count += 1
            else:
                additional_rows = ceil(time/self.maxtimestep)
                if additional_rows >4:
                    warnings.warn(f"This time step uses {additional_rows} " + \
                            "rows of the pattern. Consider using ivar")
                time_left = time
                while time_left > 0:
                    if time_left > self.maxtimestep:
                        address = None
                        time_to_write = self.maxtimestep
                        time_left -= time_to_write
                    else:
                        address = end.first_row if j == seq_len else None
                        time_to_write = time_left
                        time_left -= time_to_write
                    self.new_dpatt_str += 'writew ' + \
                        self.dig_chan_write(dig_chan) + \
                        self.time_write(int(time_to_write)) + \
                        self.address_write(
                                address = address,
                                special = None,
                                cond = None,
                                ) + \
                        self.row_num_write(comment=comment) + \
                        '\n'
                    count += 1
        #print("sequence", count, start.num_rows)

    def timebalancer(self, time, i, looplines = 2):
        timestep = self.timestep
        load_timestep = timestep
        while ((time - load_timestep)/i/timestep%looplines):
            load_timestep += timestep
        time_loop = int((time - load_timestep)/i//looplines)
        return time_loop, load_timestep


    def process_trigger_logic(self, start, end, condition):
        ivar_needed = False
        ivar_chan = None
        #Check consistency of blocks and logic and
        # Define success and failure row address.

        if condition[1:-1] == 'success':
            test_success = end.block_id
            test_failure = start.failure
        elif condition[1:-1] == 'failure':
            test_failure = end.block_id
            test_success = start.success
        start.check_consistent(success = test_success, failure = test_failure)
        if test_success == 'loop_check':
            success_row = end.loop_check_row
        else:
            success_row = self.blocks[test_success].first_row
        if test_failure == 'loop_check':
            failure_row = end.loop_check_row
        else:
            failure_row = self.blocks[test_failure].first_row

        #Determine if ivar is needed based. We set a max of r15 lines
        if start.time_span/self.maxtimestep > 1:
            ivar_needed = True
            ivar_chan, rows = self.find_good_ivar(start.time_span, 2 )
        self.new_dpatt_str += "\n#" + start.block_id + "  " + \
                              start.trigger_name +  "\n"
        #Start writing the word
        self.trigger_write(time_span = start.time_span,
                ivar_needed = ivar_needed,
                ivar_chan = ivar_chan,
                evar_chan = start.external_input-1,
                dig_chan = start.chan,
                failure_row = failure_row,
                success_row = success_row,
                num_rows = start.num_rows)
        start.written = True

    def trigger_write(self, time_span, ivar_needed, ivar_chan, evar_chan,
            dig_chan, failure_row, success_row, num_rows):
        count = 0
        if ivar_needed:
            special_load = (1<<12) + ((2**ivar_chan)<<4) + (2**evar_chan)
            special_dec = (1<<12) + ((2**ivar_chan)<<8)
            special_icheck = ((12 + ivar_chan)<<12)
            time_span_loop = time_span//self.ivars[ivar_chan]
        else:
            special_load = (1<<12) + (2**evar_chan)
            special_dec = None
        special_echeck = ((8 + evar_chan)<<12)
        special_echeck_address_failure = failure_row
        special_echeck_address_success = success_row

        # load evar
        self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            '0,' + \
                            self.address_write(
                                    address = None,
                                    special = special_load,
                                    cond = None,
                                    ) + \
                            self.row_num_write(comment='#load vars') + \
                            '\n'
        count += 1
        # Time elapse via loop or single ( min 2 just to keep same num of rows)
        if ivar_needed:
            repeat_icheck_address = self.pattern_row
            self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(time_span_loop//2) + \
                            self.address_write(
                                    address = None,
                                    special = special_dec,
                                    cond = None,
                                    ) + \
                            self.row_num_write() + \
                            '\n'

            self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(time_span_loop//2) + \
                            self.address_write(
                                    address = repeat_icheck_address,
                                    special = special_icheck,
                                    cond = None,
                                    ) + \
                            self.row_num_write() + \
                            '\n'
            count += 2
        else:
            self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            self.time_write(time_span-self.timestep) + \
                            self.address_write(
                                    address = None,
                                    special = None,
                                    cond = None,
                                    ) + \
                            self.row_num_write() + \
                            '\n'
            self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            '0,' + \
                            self.address_write(
                                    address = None,
                                    special = None,
                                    cond = None,
                                    ) + \
                            self.row_num_write() + \
                            '\n'
            count += 2

        # Check evar
        self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            '0,' + \
                            self.address_write(
                                    address = special_echeck_address_failure,
                                    special = special_echeck,
                                    cond = None,
                                    ) + \
                            self.row_num_write() + \
                            '\n'
        self.new_dpatt_str += 'writew ' + \
                            self.dig_chan_write(dig_chan) + \
                            '0,' + \
                            self.address_write(
                                    address = special_echeck_address_success,
                                    special = None,
                                    cond = None,
                                    ) + \
                            self.row_num_write() + \
                            '\n'
        count += 2
        #print("trigger", count, num_rows)

    def time_write(self, time):
        return self.w16(num=(time//self.timestep)-1, hex=False)

    def address_write(self, address = None, special = None, cond = None):
        if cond is None:
            if special is None:
                if address is None:
                    return self.w16(self.pattern_row+1, last=True) # write the next pattern
                else:
                    return self.w16(address, last=True) # write the given address
            elif (special>>12) == 1:
                return self.w16(special, last=True) # write the special load/dec command
            else:
                return self.w16(special + address, last=True)
        else:
            raise NotImplementedError(f"Conditional not implemented yet.")
            pass

    def row_num_write(self, comment = None):
        row_str = f'\t# row {self.pattern_row}'
        if comment is not None:
            row_str += f' #{comment}'
        self.pattern_row += 1
        return row_str

    def find_good_ivar(self, span, max_lines):
        min_rows = 512
        for i, val in enumerate(self.ivars):
            rows = span/self.maxtimestep/(val+1)
            if rows < min_rows:
                min_rows = rows
                good_ivar = i
            if rows < 2:
                break
        if min_rows < max_lines:
            return good_ivar, min_rows
        else:
            warnings.warn(f"No good ivar value to use < {max_lines} rows. " +
                    f"Using ivar chan {good_ivar} with {min_rows} rows.")
            return good_ivar, min_rows

    def dig_chan_write(self,chan):
        def sum_chan_bits(chan=chan, first=0, last=15):
            return sum([2**i if i>=first and i<=last else 0 for i in chan])
        out0 = sum_chan_bits(first = 0, last = 15)
        out1 = sum_chan_bits(first = 16, last = 31) >> 16
        if self.patgen_128bit:
            out2 = sum_chan_bits(first = 32, last = 47) >> 32
            out3 = sum_chan_bits(first = 48, last = 63) >> 48
            return self.w16(out0)+self.w16(out1)+self.w16(out2)+self.w16(out3)
        return self.w16(out0)+self.w16(out1)

    def process_config(self):
        b = self.blocks['control']
        self.timestep = b.timestep
        self.maxtimestep = self.timestep*65536
        if b.patgen_128bit:
            self.patgen_128bit = True
            self.config_bits += b.dacconfig<<11 #bits 12:11
            self.config_bits += b.auxline_pol<<10 # bit 10
            self.param_register = [b.start_address, b.inthreshold,
                                  *b.evars, *b.ivars, *b.dacs]
        else:
            self.patgen_128bit = False
            self.param_register = [b.start_address, *b.evars, *b.ivars]
        self.config_bits += b.clock_select<<6 # bit 7:6
        self.config_bits += b.auxconfig<<4 # bit 5:4
        self.config_bits += b.level<<1 # bit 1
        self.ivars = b.ivars
        self.evars = b.evars

    def write_config(self, other_config = 0):
        '''
        Other config bits that are not set via Control block
        bits 9:8 controlling table hooks
        bit 3 controlling RAM of writew Pattern or Params
        bit 2 controlling address reset during direct/conditional jumps
        bit 0 controlling tablereset
        '''
        config_bits = self.config_bits + other_config
        self.dpatt_str += "config " + self.w16(config_bits, last=True) + "\n"

    def write_param(self):
        self.dpatt_str += "writew "
        end = len(self.param_register)-1
        for i, val in enumerate(self.param_register):
            if i == end:
                self.dpatt_str += self.w16(val,last=True, hex=False)
            else:
                self.dpatt_str += self.w16(val, hex=False)

    def w16(self, num, last = False, hex = None):
        if hex is None:
            hex = self.hex
        assert num < 65536 and num >-1
        term = ";" if last else ","
        if hex:
            return f"{num:#06x}" + term
        else:
            return str(num) + term

# Example usage
if __name__ == "__main__":
    parser = configargparse.ArgumentParser(
            description="Loading of new Pattern Generator"
    )
    parser.add_argument(
            "--infile", "-i", default="example1.txt",
            help="Input file in correct syntax")
    parser.add_argument(
            "--outfile", "-o", default="example1.dpatt",
            help="Output file for DPG")
    parser.add_argument(
            "--hex", "-H", action="count", default=0,
            help="Write ")
    args = parser.parse_args()
    filename = args.infile
    fileout = args.outfile
    hex_mode = True if args.hex>0 else False
    p = MermaidParser(filename)
    p.parse()
    out = Translator(p.get_blocks(), p.get_logic(), filename, fileout, hex_mode)
    
