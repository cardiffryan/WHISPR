import pandas as pd
import numpy as np

#This function rounds to the nearest .025 as the ECHO only adds in .025ul increments.
def myround(x, prec=3, base=.025):
    return round(base * round(float(x)/base),prec)

def checkInputs(source_plate, mixing_table, plate_type = '384PP_AQ_BP'):

    '''

    Checks that all of the inputs are in the correct volume range for source plate type
    
    Parameters:
    -----------
    source plate: dataframe with source plate info. Columns are label, well, concentration, volume
    mixing table: dataframe with each reaction as rows and the volume of each input (columns) added to reach final reaction volume
    plate type (opt): (default = 384PP_AQ_BP) specifiy source plate type
    
    Output:
    --------
    None, error if outside of working volume range


    '''

    # check source plate type and set volume range
    if 'LDV' in plate_type:
        vol_min = 4.5
        vol_max = 14
        vol_range = vol_max - vol_min

    elif '384PP' in plate_type:
        vol_min = 20
        vol_max = 65
        vol_range = vol_max - vol_min

        
    vol = []
    for component in list(source_plate['Volume']):
        if type(component) == str:
            c = component.split(',')
            for i in c:
                vol.append(float(i))
        else:
            vol.append(component)
            
    if any([v > vol_max for v in vol]):
        raise NameError('Volumes of source plate are above working volume range.')
    if any([v < vol_min for v in vol]):
        raise NameError('Volumes of source plate are below working volume range.')





def generateVolumeTable(mixing_table_df, source_plate_df):
    '''

    Converts concentrations to volumes for reaction mixing table, raises error if volume is above max (2.5ul)
    
    Parameters:
    -----------
    source plate: dataframe with source plate info. Columns are label, well, concentration, volume
    mixing table: dataframe with each reaction as rows and the volume of each input (columns) added to reach final reaction volume
    
    Output:
    --------
    Dataframe with volumes to add of each component for each reaction


    '''

    
    vol_table = []
    vol_table_df = pd.DataFrame(columns = ['Label'] + list(source_plate_df['Label']))

    for row in mixing_table_df.index:

        vol_table_df = vol_table_df.append({'Label': row}, ignore_index = True)    
        vol = 0

        for column in mixing_table_df.columns:
            conc_to_add = float(mixing_table_df.loc[row][column])
            label_indx = 0
            conc_of_source = source_plate_df.loc[column]['Concentration'].sort_values(ascending = False)[label_indx]
            vol_to_add = myround(10*conc_to_add/conc_of_source)
            while conc_to_add > 0 and vol_to_add == 0:
                label_indx += 1
                conc_of_source = source_plate_df.loc[column]['Concentration'].sort_values(ascending = False)[label_indx]
                vol_to_add = myround(10*conc_to_add/conc_of_source)

            label = source_plate_df[source_plate_df['Concentration'] == conc_of_source].loc[column]['Label']
            vol_table_df.loc[vol_table_df['Label'] == row,label] = vol_to_add

            vol+=vol_to_add

        if vol > 2.5:
            raise NameError('Volume of '+ row+ ' exceeds 2.5ul. Total volume is '+ vol+' Please change volumes and try again.')
        else:

            vol_table_df.loc[vol_table_df['Label'] == row,'Water'] = (2.5 - vol)
            vol_table_df.loc[vol_table_df['Label'] == label,column] = vol_to_add



    return vol_table_df



def writeProtocol(plate_type, vol_table, source_plate_layout, output_layout,source_plate_df):
	'''
	Writes protocol for use with ECHO plate reader

	Parameters:
	----------
	 - plate_type: Source plate calibration (str)
	 - mixing_table: path to csv file with reaction volumes (str)
	 - input_layout: links inputs to source well (dict)
	 - output_layout: path to csv with desired plate layout for 96 well plate (str)
	 
	 
	Returns:
	--------
	 - dataframe of ECHO protocol


	Reference slides here for more information: 
	https://docs.google.com/presentation/d/1VzEFFiyCCfI-mrfSQGjb41TOOcz61sTlfk1WMnb-7BI/edit#slide=id.gf541592c34_0_28
	'''

        # check source plate type and set volume range
    if 'LDV' in plate_type:
        vol_range = 9.5
    elif '384PP' in plate_type:
        vol_range = 45

    # keep track of volume used for each component
    vol_used = {}
    for k in list(vol_table.columns[1:]):
        vol_used[k] = 0


    # reads plate layout and assigns wells to each reaction (rxn_loc; dict)
    plate = pd.read_csv(output_layout, index_col = 0, dtype = str) 
    labels = pd.unique(np.concatenate(plate.values))
    rxn_loc = {}
    for l in labels:
        if type(l) is str:
            index = plate[plate.isin([l])].stack().index
            rxn_loc[l] = []
            for i in index:
                rxn_loc[l].append(str(i[0]) + i[1])



    # create output dataframe
    output_df = pd.DataFrame(columns = {'Source Plate Name', 'Source Plate Type', 'Source Well', 
                                     'Destination Plate Name', 'Destination Well', 'Transfer Volume'})


    '''
    for each reaction in the plate layout:
        if this reaction label matches one in the mixing table:
            for each well of the reaction in the plate layout:
                for each component in the reaction:
                    find volume to transfer of component
                    if any volume is added:
                        if there is one source well:
                            if the volume used of this component is less than the volume range:
                                append row
                        if there is more than one source well:
                            if the volume used of this component is less than the volume range:
                                append row
                            else:
                                remove first source well
                                append row
                        update volume used
                        append output dataframe                    

    ''' 


    # subtract from volume in source plate file 

    rxn_keys = list(rxn_loc.keys())
    for rxn in rxn_keys:
        if rxn in list(vol_table['Label']): 
            for well in rxn_loc[rxn]: 
                vols = vol_table[vol_table['Label'] == rxn]
                for component in vols.columns[1:]: 
                    transfer_vol = float(vols[component])
                    if transfer_vol > 0:
                    ## separate if there is > 1 well in source plate
                        source_well = list(source_plate_df[source_plate_df['Label'] == component]['Well'])
                        source_well = source_well[0].split(',')

                         ## use first well unless the well is empty, then use second well

                        if vol_used[component] + transfer_vol >= vol_range:
                            #need to check length of source_well and throw error
                            vol_used[component] = 0
                            source_well = source_well[1:]
                            if len(source_well) == 0:
                                raise NameError('Need more volume of ' +component+ ' to complete reaction. Add another well to source plate.')
                        row = {'Source Plate Name':'Source[1]', 'Source Plate Type': plate_type, 'Source Well': source_well[0],
                            'Destination Plate Name':'Destination[1]', 'Destination Well': well, 'Transfer Volume': transfer_vol*1000}


                        vol_used[component] = vol_used[component] + transfer_vol

                        output_df = output_df.append(row, ignore_index = True)


    output_df = output_df[['Source Plate Name', 'Source Plate Type', 'Source Well', 
                            'Destination Plate Name', 'Destination Well', 'Transfer Volume']]





    print('\n')
    for component in vol_used:
        if 'LDV' in plate_type:
            print('Load at least ', np.round(4.5+vol_used[component],2), 'ul and maximum 14 ul of ', component)
        elif '384PP' in plate_type:
            print('Load at least ', np.round(20+vol_used[component],2), 'ul and maximum 65 ul of ', component)



    return(output_df)