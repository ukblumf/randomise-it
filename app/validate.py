from flask import g
from flask_login import current_user
import re
from .models import RandomTable, Macros
from .randomise_utils import split_id, get_random_table_record, get_macro_record


def check_table_definition_validity(table):
    error_message = ''
    table_list = table.definition.splitlines()
    table_iter = iter(table_list)
    validate_table_definition = True
    min_rng = 99999999
    max_rng = 0
    with_line_numbers = 0
    without_line_numbers = 0
    number_of_rows = 0
    table_line_type = 1  # Set table type to 1, meaning with line numbers on rows
    for i in table_iter:
        if i.count('::') == 1:
            with_line_numbers += 1
        elif i.count('::') == 0:
            without_line_numbers += 1
        number_of_rows += 1

    if with_line_numbers and without_line_numbers:
        error_message = 'Table definition invalid, mixed line numbers on rows'
        return 0, 0, False, 0, error_message

    if without_line_numbers:
        table_line_type = 0
        min_rng = 1
        max_rng = number_of_rows

    table_iter = iter(table_list)

    # validate table definition
    for line_number, i in enumerate(table_iter):
        # check number of ::
        if (i.count('::') != 1 and table_line_type == 1) or (i.count('::') != 0 and table_line_type == 0):
            validate_table_definition = False
            error_message = 'Invalid number of separators on line ' + i + ", line number: " + str(line_number)
            break
        row_text = i
        if table_line_type == 1:
            # split line
            line_def = i.split('::')
            if not bool(re.search(r'^\d+-\d+$', line_def[0])):
                if not bool(re.search(r'^\d+$', line_def[0])):
                    validate_table_definition = False
                    error_message = 'Invalid number/number range on line ' + i + ", line number: " + str(line_number)
                    break
            if bool(re.search(r'^\d+-\d+$', line_def[0])):
                match_values = re.search(r'^(\d+)-(\d+)$', line_def[0])
                if int(match_values.group(1)) > int(match_values.group(2)):
                    validate_table_definition = False
                    error_message = 'Invalid range, first number greater than second on line ' + i + ", line number: " + str(
                        line_number)
                    break
                else:
                    if int(match_values.group(1)) < min_rng:
                        min_rng = int(match_values.group(1))
                    if int(match_values.group(2)) > max_rng:
                        max_rng = int(match_values.group(2))
            if bool(re.search(r'^\d+$', line_def[0])):
                match_values = re.search(r'^(\d+)$', line_def[0])
                if int(match_values.group(1)) < min_rng:
                    min_rng = int(match_values.group(1))
                if int(match_values.group(1)) > max_rng:
                    max_rng = int(match_values.group(1))
            row_text = line_def[1]

        if validate_table_definition:
            validate_table_definition, error_message = validate_text(row_text, table.id)
            error_message += ", line number: " + str(line_number + 1)

    return max_rng, min_rng, validate_table_definition, table_line_type, error_message, number_of_rows


def validate_text(definition, id):
    error_message = ''
    validate_definition = True
    if definition.find("macro." + id) >= 0:
        validate_definition = False
        error_message = "Macro referencing self"
    elif definition.count('<<') != definition.count('>>'):
        validate_definition = False
        error_message += 'External reference is malformed in macro'
    elif definition.count('<<'):
        open_angle_brackets = definition.find("<<")
        while open_angle_brackets >= 0:
            close_angle_brackets = definition.find(">>", open_angle_brackets)

            external_id = definition[open_angle_brackets + 2:close_angle_brackets]
            external_data = None
            username, id_type, reference_id = split_id(external_id)

            if id_type == 'table':
                external_data = get_random_table_record(username, reference_id)
            elif id_type == 'macro':
                external_data = get_macro_record(username, reference_id)

            if external_data is None:
                error_message += '\nExternal reference <<' + external_id + '>> not found'
                return False, error_message
            open_angle_brackets = definition.find("<<", close_angle_brackets)

    if definition.count('((') != definition.count('))'):
        validate_definition = False
        error_message += '\nRandom Number range is malformed'
    if definition.count('((') > 0:
        open_brackets = definition.find("((")

        while open_brackets >= 0:
            close_brackets = definition.find("))", open_brackets)
            generator = definition[open_brackets + 2:close_brackets]
            # check type of generator
            if not bool(re.search(r'^\d+d\d+$', generator, re.IGNORECASE)):  # e.g 1d6
                if not bool(re.search(r'^\d+d\d+x\d+$', generator, re.IGNORECASE)):  # e.g. 1d6x10
                    if not bool(re.search(r'^\d+d\d+\+\d+$', generator, re.IGNORECASE)):  # e.g. 2d4+2
                        if not bool(re.search(r'^\d+d\d+\-\d+$', generator, re.IGNORECASE)):  # e.g. 4d4-1
                            if not bool(re.search(r'^\d+-\d+$', generator, re.IGNORECASE)):  # e.g. 1-100
                                if not bool(re.search(r'^\d+-\d+x\d+$', generator, re.IGNORECASE)):  # e.g. 1-100x10
                                    if not bool(re.search(r'^\d+d\d+x<<table\..*?>>$', generator,
                                                          re.IGNORECASE)):  # e.g. 1d6x<<table.magic-item-table-a>>
                                        if not bool(re.search(r'^\d+-\d+x<<table\..*?>>$', generator,
                                                              re.IGNORECASE)):  # e.g. 1-10x<<table.magic-item-table-a>>
                                            if bool(re.search(r'(\d+d\d+|\d+|[\+|\-])', generator, re.IGNORECASE)):
                                                components = re.finditer(r'(\d+d\d+|\d+|[\+|\-])', generator, re.IGNORECASE)
                                                valid_generator = True
                                                expect_value = True
                                                operand = 1
                                                for component in components:
                                                    if expect_value:
                                                        expect_value = False
                                                        if re.search(r'd', component.group(1), re.IGNORECASE):
                                                            # dice notation
                                                            if not bool(re.search(r'^(\d+)d(\d+)', component.group(1), re.IGNORECASE)) and not bool(re.search(r'\d+', component.group(1), re.IGNORECASE)):
                                                                valid_generator = False
                                                                break
                                                    else:
                                                        expect_value = True
                                                        if component.group(1) != '+' and component.group(1) != '-':
                                                            valid_generator = False
                                                            break
                                                if not valid_generator:
                                                    error_message += '\nRandom number in ((' + generator + ')) not recognised'
                                                    validate_definition = False
            open_brackets = definition.find("((", close_brackets)

    return validate_definition, error_message


def validate_collection(items):
    error_message = ''
    validate = True

    for item in items.splitlines():
        external_data = None
        checked = False
        user_id = 0
        if hasattr(g, 'current_user'):
            user_id = g.current_user.id
        else:
            user_id = current_user.id

        if item.startswith('table.'):
            checked = True
            external_data = RandomTable.query.get([item[6:], user_id])
        elif item.startswith('macro.'):
            checked = True
            external_data = Macros.query.get([item[6:], user_id])

        if external_data is None and checked:
            error_message += '\nExternal reference ' + item + ' not recognised.'
            validate = False

    return validate, error_message
