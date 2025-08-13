
# Define defect type here. Within each elements, it contains 3 info:
# 1. Name, 2. Display Color (Display Color is the color used for visualization), 3. Annotated Color (Annotated color is the RGB color defined in masks)
# The 0th index must be Background, and its Annotated color is not required to be defined. Hence, any color not used by other features will be treated as Background color.

def feature_type():

	feature = [	['Background',(255,255,255)],                            	#class 0
					['Crack',(179, 71, 71) ,(179, 71, 71)],                		#class 1
					['Bsht_scratch' ,(143, 179, 71) ,(143, 179, 71)],      		#class 2
					['Dark_spot' ,(71, 179, 71) ,(71, 179, 71)],                #class 3
					['Finger_defect' ,(147, 205, 215) ,(147, 205, 215)],        #class 4
					['Vegetation' ,(72, 179, 143) ,(72, 179, 143)],             #class 5
					['Dark_bleed' ,(71, 71, 179) ,(71, 71, 179)],             	#class 6
					['Corner_stain' ,(143, 71, 179) ,(143, 71, 179)],         	#class 7
					['Small_animal' ,(138, 108, 103) ,(138, 108, 103)],         #class 8
					['Bird_drop' ,(218, 0, 150) ,(218, 0, 150)],  				#class 9
					['Object_on_top' ,(179, 71, 143) ,(179, 71, 143)],          #class 10
					['Cable' ,(255, 126, 0) ,(255, 126, 0)],          			#class 11
					['Busbar_darkening',(236, 231, 185), (236, 231, 185)],		#class 12
					['Bright_pocket', (47, 230, 232), (47, 230, 232)],			#class 13
					['Dark_edge', (241, 188, 133), (241, 188, 133)],			#class 14
					['Cross_crack' ,(255, 0, 0) ,(255, 0, 0)],					#class 15
					['Dark_horizontal_line', (155, 252, 112), (155, 252, 112)],	#class 16
					['Dark_area', (71, 143, 179), (71, 143, 179)],				#class 17
					['Dark_circle', (191, 230, 200), (191, 230, 200)],			#class 18
					['Dark_vertical_line', (220, 215, 235), (220, 215, 235)]	#class 19
					]                  
				
	
	return feature
