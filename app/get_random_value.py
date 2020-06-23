from .randomise_utils import get_random_table_record, get_macro_record
import random
import re


def process_text_extended(text):
    def char_check(char):
        if i < len(text)-7:
            if text[i] == char and text[i+1] == char:
                return True
        return False

    def extract_enclosed_text(close_char):
        closing_position = text.find(close_char + close_char, i)
        if closing_position >= 0:
            return text[i + 2:closing_position], closing_position
        return "", -1

    i = 0
    loop_control = {}
    new_text = ''

    while True:
        #  check for dice, enclosed by (( ))
        if char_check('('):
            enclosed_text, cursor_position = extract_enclosed_text(')')
            if enclosed_text:
                generated_text = dice_generator(enclosed_text).rstrip(' ').rstrip(',')
                if generated_text:
                    new_text += generated_text
                    i = cursor_position + 2

        #  Check for external reference (table or macro), enclosed by << >>
        elif char_check('<'):
            enclosed_reference, cursor_position = extract_enclosed_text('>')
            if enclosed_reference:
                generated_text = extract_reference_link(enclosed_reference).rstrip(' ').rstrip(',')
                new_text += generated_text
                i = cursor_position + 2

        #  Check for programming directive, enclosed by [[ ]]
        elif char_check('['):
            command, cursor_position = extract_enclosed_text(']')
            directive, param = command.split(':')
            if directive == 'LOOP':
                if param not in loop_control:
                    #  store name of loop, cursor position and iteration count=0
                    loop_control[param] = [cursor_position + 2, 1]
                    i = cursor_position + 2
            elif directive == 'ENDLOOP':
                #  check if loop exists
                loop_name, max_value = param.split('=')
                if loop_name in loop_control:
                    if loop_control[loop_name][1] < int(max_value):
                        loop_control[loop_name][1] += 1
                        i = loop_control[loop_name][0]
                    else:
                        del loop_control[loop_name]
                        i = cursor_position + 2

        else:
            if i >= len(text):
                break
            new_text += text[i]
            i += 1
            if i >= len(text):
                break

    return new_text


def dice_generator(dice_pattern):
    generated_text = ''
    value = 0
    # what type of generator
    if bool(re.search(r'^\d+d\d+$', dice_pattern, re.IGNORECASE)):
        # Found dice type random number
        dice = re.search(r'^(\d+)d(\d+)$', dice_pattern, re.IGNORECASE)
        # Comprising number of dice in dice.group(1))
        # And dice size in dice.group(2))
        for d in range(int(dice.group(1))):
            value += random.randint(1, int(dice.group(2)))
        generated_text = str(value)

    elif bool(re.search(r'^\d+d\d+x\d+$', dice_pattern, re.IGNORECASE)):
        # Found dice type random number with multiplier
        dice = re.search(r'^(\d+)d(\d+)', dice_pattern, re.IGNORECASE)
        multiplier = re.search(r'x(\d+)$', dice_pattern, re.IGNORECASE)
        # Number of dice in dice.group(1))
        # Dice size in dice.group(2))
        # Multiplier in multiplier.group(1))
        for d in range(int(dice.group(1))):
            value += random.randint(1, int(dice.group(2)))
        value *= int(multiplier.group(1))
        generated_text = str(value)

    elif bool(re.search(r'^\d+d\d+\+\d+$', dice_pattern, re.IGNORECASE)):
        # Found dice type random number with addition
        dice = re.search(r'^(\d+)d(\d+)', dice_pattern, re.IGNORECASE)
        addend = re.search(r'\+(\d+)$', dice_pattern, re.IGNORECASE)
        # Number of dice in dice.group(1))
        # Dice size in dice.group(2))
        # Added number in multiplier.group(1))
        for d in range(int(dice.group(1))):
            value += random.randint(1, int(dice.group(2)))
        value += int(addend.group(1))
        generated_text = str(value)

    elif bool(re.search(r'^\d+d\d+\-\d+$', dice_pattern, re.IGNORECASE)):
        # Found dice type random number with subtraction
        dice = re.search(r'^(\d+)d(\d+)', dice_pattern, re.IGNORECASE)
        subtraend = re.search(r'\-(\d+)$', dice_pattern, re.IGNORECASE)
        # Number of dice in dice.group(1))
        # Dice size in dice.group(2))
        # Added number in multiplier.group(1))
        for d in range(int(dice.group(1))):
            value += random.randint(1, int(dice.group(2)))
        value += int(subtraend.group(1))
        generated_text = str(value)

    elif bool(re.search(r'^\d+-\d+$', dice_pattern, re.IGNORECASE)):
        # Found range type random number
        rng = re.search(r'^(\d+)-(\d+)$', dice_pattern, re.IGNORECASE)
        # Min range in rng.group(1))
        # Max range in rng.group(2))
        value = random.randint(int(rng.group(1)), int(rng.group(2)))
        generated_text = str(value)

    elif bool(re.search(r'^\d+-\d+x\d+$', dice_pattern, re.IGNORECASE)):
        # Found range type random number with multiplier
        rng = re.search(r'^(\d+)-(\d+)', dice_pattern, re.IGNORECASE)
        multiplier = re.search(r'x(\d+)$', dice_pattern, re.IGNORECASE)
        # Min range in rng.group(1)
        # Max range in rng.group(2))
        # Multiplier in multiplier.group(1))
        value = random.randint(int(rng.group(1)), int(rng.group(2)))
        value *= int(multiplier.group(1))
        generated_text = str(value)

    elif bool(re.search(r'^\d+d\d+x<<.*?>>$', dice_pattern, re.IGNORECASE)):
        # found dice type random number with external reference
        dice = re.search(r'^(\d+)d(\d+)', dice_pattern, re.IGNORECASE)
        external_table = re.search(r'x<<(.*?)>>$', dice_pattern, re.IGNORECASE)
        # number of dice IN dice.group(1)
        # dice size IN dice.group(2)
        # external table in external_table.group(1)
        for d in range(int(dice.group(1))):
            roll = random.randint(1, int(dice.group(2)))
            for n in range(roll):
                generated_text += get_text_from_external_table(external_table.group(1)) + ", "

    elif bool(re.search(r'^\d+-\d+x<<.*?>>$', dice_pattern, re.IGNORECASE)):
        # Found range type random number with external reference
        rng = re.search(r'^(\d+)-(\d+)', dice_pattern, re.IGNORECASE)
        # Min range in rng.group(1))
        # Max range in rng.group(2))
        external_table = re.search(r'x<<(.*?)>>$', dice_pattern, re.IGNORECASE)
        # External table in external_table.group(1))
        roll = random.randint(int(rng.group(1)), int(rng.group(2)))
        for n in range(roll):
            generated_text += get_text_from_external_table(external_table.group(1)) + ","

    elif bool(re.search(r'(\d+d\d+|\d+|[\+|\-])', dice_pattern, re.IGNORECASE)):
        # found chained dice and static numbers to produce sum
        components = re.finditer(r'(\d+d\d+|\d+|[\+|\-])', dice_pattern, re.IGNORECASE)
        result = 0
        expect_value = True
        operand = 1
        for component in components:
            if expect_value:
                expect_value = False
                if re.search(r'd', component.group(1), re.IGNORECASE):
                    # dice notation
                    dice = re.search(r'^(\d+)d(\d+)', component.group(1), re.IGNORECASE)
                    for d in range(int(dice.group(1))):
                        result += (random.randint(1, int(dice.group(2))) * operand)
                elif re.search(r'\d+', component.group(1), re.IGNORECASE):
                    # static number
                    result += (int(component.group(1)) * operand)
            else:
                expect_value = True
                if component.group(1) == '+':
                    operand = 1
                elif component.group(1) == '-':
                    operand = -1

        generated_text = str(result)

    return generated_text


def extract_reference_link(external_id):
    if bool(re.search(r'^\d+%\s', external_id)):
        chance = re.search(r'^(^\d+)%\s(.*)$', external_id)
        # Found chance in chance.group(1))
        if random.randint(1, 100) <= int(chance.group(1)):
            # Chance succeeded
            external_id = chance.group(2)
        else:
            return None

    return get_text_from_external_table(external_id)


def get_text_from_external_table(external_id):
    generated_text = 'Problem with ' + external_id
    username, id_type, ident = external_id.split('.')

    if id_type == 'table':
        table = get_random_table_record(username, ident)
        if table is not None:
            generated_text = get_row_from_random_table_definition(table)
        else:
            generated_text = 'error reading from ' + external_id

    if id_type == 'macro':
        macro = get_macro_record(username, ident)
        if macro is not None:
            generated_text = process_text_extended(macro.definition)
        else:
            generated_text = 'error reading from ' + external_id

    return generated_text


def get_row_from_random_table_definition(table):
    min_rng = table.min
    max_rng = table.max
    table_list = table.definition.splitlines()
    table_iter = iter(table_list)
    random_number = random.randint(min_rng, max_rng)
    selected_text = ''
    # get row from table
    if table.line_type == 1:
        for i in table_iter:
            line_def = i.split('::')
            if bool(re.search(r'^\d+-\d+$', line_def[0])):
                match_values = re.search(r'^(\d+)-(\d+)$', line_def[0])
                if int(match_values.group(1)) <= random_number <= int(match_values.group(2)):
                    selected_text = line_def[1]
                    break
            else:
                if int(line_def[0]) == random_number:
                    selected_text = line_def[1]
                    break
    else:
        selected_text = table_list[random_number - 1]

    return process_text_extended(selected_text)
