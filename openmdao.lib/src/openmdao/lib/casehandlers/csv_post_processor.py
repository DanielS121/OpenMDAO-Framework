"""
    Post-processing function that takes a case_data_set and outputs a csv file
"""

import csv

def caseset_query_to_csv(data, cds, filename='cases.csv', delimiter=',', quotechar='"'):
    """
    Post-processing function that takes a case_data_set and outputs a csv file
    Should be able to pass tests of current csv case recorder (column ordering, meta column, etc...)
    Assume query by case (not variable)

    Inputs:

    data - results of fetch on Query object
    cds - CaseDataset

    """

    drivers = {}
    for driver in cds.drivers:
        drivers[driver['_id']] = driver['name']

    # Determine inputs & outputs, map pseudos to expression names.
    expressions = cds.simulation_info['expressions']
    metadata = cds.simulation_info['variable_metadata']
    constants_names = cds.simulation_info['constants'].keys()
    inputs = []
    outputs = []
    pseudos = {}
    for name in sorted(metadata.keys()):
        if name in constants_names:
            continue
        if name in metadata:
            if metadata[name]['iotype'] == 'in':
                inputs.append(name)
            else:
                outputs.append(name)
        elif '_pseudo_' in name:
            for exp_name, exp_dict in expressions.items():
                if exp_dict['pcomp_name'] == name:
                    pseudos[name] = '%s(%s)' % (exp_dict['data_type'], exp_name)
                    break
            else:
                raise RuntimeError('Cannot find %r in expressions' % name)
            outputs.append(name)
        else:
            outputs.append(name)

    sorted_inputs = sorted( inputs )
    sorted_outputs = sorted( outputs )

    # Open CSV file
    outfile = open(filename, 'w')
    csv_writer = csv.writer(outfile, delimiter=delimiter,
                                     quotechar=quotechar,
                                     quoting=csv.QUOTE_NONNUMERIC)
    # No automatic data type conversion is performed unless the QUOTE_NONNUMERIC format option is specified (in which case unquoted fields are transformed into floats).

    # Write the headers
    headers = ['timestamp', '/INPUTS']
    headers.extend(sorted_inputs)
    headers.append('/OUTPUTS')
    headers.extend(sorted_outputs)
    headers.extend(['/METADATA', 'uuid', 'parent_uuid', 'msg'])
    csv_writer.writerow(headers)

    # Write the data
    # data is a list of lists where the inner list is the values and metadata for a case
    #var_names = cds.data.var_names().fetch() # the list of names of the values in the case list

    for i, row in enumerate( data ):
        if i == 0:
            var_names = row.name_map.keys()

        csv_data = []

        csv_data.append( row[ row.name_map[ 'timestamp' ] ] )
        csv_data.append('')
        if inputs:
            for name in sorted_inputs:
                value = row[row.name_map[name]]
                import pdb; pdb.set_trace()
                if value in ['True','False']:
                    value = str(value)
                csv_data.append( value )
        csv_data.append('')
        if outputs:
            for name in sorted_outputs:
                if name == '_driver_id':
                    value = drivers[row[row.name_map[name]]]
                else:
                    value = row[row.name_map[name]]
                csv_data.append( row[row.name_map[name]] )
        case_uuid = row[ row.name_map[ '_id' ] ]
        parent_uuid = row[ row.name_map[ '_parent_id' ] ]
        msg = row[ row.name_map[ 'error_message' ] ]
        csv_data.extend(['', case_uuid, parent_uuid, msg])

        csv_writer.writerow(csv_data)

    outfile.close()


