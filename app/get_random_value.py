from .randomise_utils import get_random_table_record, get_macro_record
import random
import re

var_control = {}


def process_text_extended(text):
    def char_check(char):
        if i < len(text)-6:
            if text[i] == char and text[i+1] == char:
                return True
        return False

    def extract_enclosed_text(close_char):
        nonlocal i
        nonlocal text
        nonlocal opening_commands
        global var_control
        closing_position = text.find(close_char + close_char, i)
        if closing_position >= 0:
            if close_char == ']':
                opening_commands -= 1
                find_embedded_command = text[i:closing_position].find('[[', 0)
                if find_embedded_command >= 0:
                    opening_commands += text[i:closing_position].count('[[')
                    find_embedded_command += i
                    text = text[:find_embedded_command+2] + text[find_embedded_command+2:closing_position].replace(':', '§') + text[closing_position:]
                    tmp_i = i
                    i = closing_position+2
                    _, closing_position = extract_enclosed_text(']')
                    i = tmp_i
                else:
                    tmp_i = i
                    while opening_commands > 0:
                        text = text[:tmp_i] + text[tmp_i:closing_position].replace(':', '§') + text[closing_position:]
                        opening_commands -= 1
                        if opening_commands > 0:
                            tmp_i = closing_position + 2
                            closing_position = text.find(']]', tmp_i)
                        else:
                            closing_position += 2

                return text[i:closing_position], closing_position
            else:
                return text[i:closing_position], closing_position
        return "", -1

    i = 0
    loop_control = {}
    new_text = ''
    opening_commands = 0
    while True:
        increment = True
        #  check for dice, enclosed by (( ))
        if char_check('('):
            i += 2
            enclosed_text, cursor_position = extract_enclosed_text(')')
            if enclosed_text:
                generated_text = dice_generator(enclosed_text).rstrip(' ').rstrip(',')
                if generated_text:
                    new_text += generated_text
                    i = cursor_position + 2
                    increment = False
        #  Check for external reference (table or macro), enclosed by << >>
        elif char_check('<'):
            i += 2
            enclosed_reference, cursor_position = extract_enclosed_text('>')
            if enclosed_reference:
                generated_text = extract_reference_link(enclosed_reference).rstrip(' ').rstrip(',')
                new_text += generated_text
                i = cursor_position + 2
                increment = False

        #  Check for programming directive, enclosed by [[ ]]
        elif char_check('['):
            opening_commands = 1
            i += 2
            command, cursor_position = extract_enclosed_text(']')
            command_list = iter(command.split(':'))
            directive = next(command_list)
            params = [param for param in command_list]

            if directive == 'LOOP':
                if params[0] not in loop_control:
                    #  store name of loop, cursor position and iteration count=1
                    loop_control[params[0]] = [cursor_position + 2, 1]
                    i = cursor_position + 2
                    increment = False
            elif directive == 'ENDLOOP':
                loop_name, max_value = params[0].split('=')
                if loop_name in loop_control:
                    if loop_control[loop_name][1] < int(max_value):
                        loop_control[loop_name][1] += 1
                        i = loop_control[loop_name][0]
                        increment = False
                    else:
                        del loop_control[loop_name]
                        i = cursor_position + 2
                        increment = False
            elif directive == 'IF':
                chance = 0
                true_condition = ""
                false_condition = ""
                if len(params) == 2:
                    chance, true_condition = params
                else:
                    chance, true_condition, false_condition = params
                if random.randint(1, 100) <= int(chance.strip('%')):
                    new_text += process_text_extended(true_condition.replace('§', ':'))
                elif false_condition is not None:
                    new_text += process_text_extended(false_condition.replace('§', ':'))
                i = cursor_position + 2
                increment = False
            elif directive == 'CHOICE':
                new_text += process_text_extended(params[random.randint(0, len(params)-1)].replace('§', ':'))
                i = cursor_position + 2
                increment = False
            elif directive == 'VAR':
                if len(params) == 2:
                    #  setting variable
                    var_control[params[0]] = process_text_extended(params[1].replace('§', ':'))
                else:
                    if params[0] in var_control:
                        new_text += var_control[params[0]]
                    else:
                        new_text += "missing variable " + params[0]
                i = cursor_position + 2
                increment = False

        if increment:
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

    elif bool(re.search(r'^\d+x<<.*?>>$', dice_pattern, re.IGNORECASE)):
        # Found static number with external reference
        num = re.search(r'^(\d+)', dice_pattern, re.IGNORECASE)
        # number in num.group(1))
        external_table = re.search(r'x<<(.*?)>>$', dice_pattern, re.IGNORECASE)
        # External table in external_table.group(1))
        for n in range(int(num.group(1))):
            generated_text += get_text_from_external_table(external_table.group(1)) + ","

    elif bool(re.search(r'(\d+d\d+|\d+|[\+|\-|x])', dice_pattern, re.IGNORECASE)):
        # found chained dice and static numbers to produce sum
        components = re.finditer(r'(\d+d\d+|\d+|[\+|\-|x])', dice_pattern, re.IGNORECASE)
        result = 0
        expect_value = True
        operand = "+"
        for component in components:
            if expect_value:
                expect_value = False
                if re.search(r'd', component.group(1), re.IGNORECASE):
                    # dice notation
                    dice = re.search(r'^(\d+)d(\d+)', component.group(1), re.IGNORECASE)
                    dice_sum = 0
                    for d in range(int(dice.group(1))):
                        dice_sum += random.randint(1, int(dice.group(2)))
                    result = apply_operand(result, dice_sum, operand)
                elif re.search(r'\d+', component.group(1), re.IGNORECASE):
                    # static number
                    result = apply_operand(result, int(component.group(1)), operand)
            else:
                expect_value = True
                operand = component.group(1)

        generated_text = str(result)

    return generated_text


def apply_operand(current_total, value, operand):
    if operand == "+":
        current_total += value
    elif operand == "-":
        current_total -= value
    elif operand == "x":
        current_total *= value
    return current_total


def extract_reference_link(external_id):
    if bool(re.search(r'^\d+%\s', external_id)):
        chance = re.search(r'^(^\d+)%\s(.*)$', external_id)
        # Found chance in chance.group(1))
        if random.randint(1, 100) <= int(chance.group(1)):
            # Chance succeeded
            external_id = chance.group(2)
        else:
            return ""

    return get_text_from_external_table(external_id)


def get_text_from_external_table(external_id):
    generated_text = 'Problem with ' + external_id
    try:
        username, id_type, ident = external_id.split('.')
    except Exception as e:
        return generated_text

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


def get_row_from_random_table_definition(table, modifier=0):
    min_rng = table.min
    max_rng = table.max
    table_list = table.definition.splitlines()
    table_iter = iter(table_list)
    random_number = random.randint(min_rng, max_rng) + modifier
    if random_number < min_rng:
        random_number = min_rng
    elif random_number > max_rng:
        random_number = max_rng
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
