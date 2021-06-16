#-------------------------------------------------------------------------------
# Name:        Split Line From Distamce
# Purpose:     Project HRIS
# Created:     19/01/2021
# Copyright:   (c) Infraplus 2021
# Licence:     sittinun2tb@gmail.com & kittiwan.sati@gmail.com(support)
#-------------------------------------------------------------------------------

import os, sys, numpy
import shapefile

from shapely.wkb import loads
from shapely.geometry import Polygon, LineString, Point, asLineString, shape, mapping
from shapely.ops import substring
from shapely.geometry import CAP_STYLE
import fiona
import logging
import geopandas as gpd
import subprocess
import os


# D:\infraplus\HRIS\survey_data\2021-02-19\20210219_338_00040501
path_in= str(input('path_input ='))
k_start= int(input('km_str ='))
k_end = int(input('km_end ='))

dir_app = os.path.dirname(sys.argv[0])
inpath = os.path.join(dir_app, "%s" %(path_in))
outpath = os.path.join(dir_app, "%s\clip_buffer_output" %(path_in))

os.mkdir(r'%s\clip_buffer_output' %(path_in))
os.mkdir(r'%s\clip_buffer_output\export_section' %(path_in))
os.mkdir(r'%s\clip_pointcloud_output' %(path_in))
os.mkdir(r'%s\converter_potree_output' %(path_in))


list_field = []
newline = []

f_n = path_in[41:63]

# https://gis.stackexchange.com/questions/203048/split-lines-at-points-using-shapely
# https://shapely.readthedocs.io/en/stable/manual.html

class RawShapefile():
    def __init__(self, DISTm, BUFFm):
        self.indir = os.path.join(inpath, "%s_1.shp" %(f_n))
        self.indbf = os.path.join(inpath, "%s_1.dbf" %(f_n))

        self.outdir = os.path.join(outpath, "%s_1.shp" %(f_n))
        self.bufdir = os.path.join(outpath, "%s_1_clip_buff.shp"%(f_n))
        self.pntdir = os.path.join(outpath, "%s_1_point.shp"%(f_n))
        self.DISTm = DISTm
        self.BUFFm = BUFFm

    def test(self):
        print(self.indir)

    def geoToUTM(self, item):
        geom_array = tuple(numpy.asarray(item))
        xy_array = [transform(self.pj_wgs84, self.pj_utm47, lon, lat) for lon, lat in geom_array]
        ds_utm = LineString(xy_array)
        return ds_utm

    def process(self):
        shpReader = shapefile.Reader(shp=open(self.indir, 'rb'), dbf=open(self.indbf, 'rb'))
        dbfResder = shpReader.fields

        if shpReader.shapeType == 0:
            print('Geometry Type = NULL')
        elif shpReader.shapeType == 1:
            print('Geometry Type = POINT')
        elif shpReader.shapeType == 3:
            print('Geometry Type = LineString')
        elif shpReader.shapeType == 13:
            print('Geometry Type = POLYLINEZ')
        else:
            print("NNNNNNNNNNN")

        for field in dbfResder[1:]:
            list_field.append(field[0])

        # Define a Line feature geometry with one attribute
        schema_line = {
            'geometry': 'LineString',
            'properties': {'section_part_id': 'int', 'km_start': 'int', 'km_end': 'int', 'length': 'float'}
        }

        schema_buff = {
            'geometry': 'Polygon',
            'properties': {'section_part_id': 'int', 'buffer_m': 'float'}
        }

        schema_pnt = {
            'geometry': 'Point',
            'properties': {'section_part_id': 'int', 'km_m': 'str'}
        }

        with fiona.open(self.outdir, 'w', 'ESRI Shapefile', schema_line) as outshp:

            for i in shpReader.shapeRecords():
                # print ("Road Object: %s" % i)
                attribute = dict(zip(list_field, i.record))
                attribute['the_geom'] = i.shape
                arr_point = attribute['the_geom'].points
                km_s = attribute['km_start']
                obj_utm = asLineString(arr_point)

                distance_m = obj_utm.length
                print('Geometry Length = %s' % distance_m)

                j = 0.0

                while j < distance_m:
                    # print (j, distance_m)
                    # p = obj_utm.interpolate(j) #obj_utm.interpolate(j, normalized=True)
                    s = substring(obj_utm, j, j + self.DISTm)
                    # print (s)
                    newline.append(s)
                    j = j + self.DISTm
                    # break
                # else:
                #    if j >= distance_m:
                #        j = j-self.DISTm
                #    s = substring(obj_utm, j, distance_m)
                #    newline.append(s)

                print("Road Object Split Count : %s" % len(newline))

                km_start = km_s
                km_end = self.DISTm

                for k, v in enumerate(newline):
                    # print (k+1, v, v.length)
                    section_part_id = k + 1
                    if section_part_id == len(newline):
                        km_end = km_start + v.length
                    try:
                        outshp.write({
                            'geometry': mapping(v),
                            'properties': {'section_part_id': section_part_id, 'km_start': km_start, 'km_end': km_end,
                                           'length': v.length}
                        })
                        section_part_id = section_part_id + 1
                        km_start = km_end
                        km_end = km_start + self.DISTm
                    except:
                        logging.exception("Error processing feature %s:", k)
            # Close
            outshp.closed

        with fiona.open(self.bufdir, 'w', 'ESRI Shapefile', schema_buff) as bufshp:

            for k, v in enumerate(newline):
                # print (k+1, v, v.length)
                buf = v.buffer(self.BUFFm, resolution=16, cap_style=2)
                try:
                    bufshp.write({
                        'geometry': mapping(buf),
                        'properties': {'section_part_id': k + 1, 'buffer_m': self.BUFFm}
                    })
                    k = k + 1
                except:
                    logging.exception("Error processing feature %s:", k)
            # Close
            bufshp.closed

        with fiona.open(self.pntdir, 'w', 'ESRI Shapefile', schema_pnt) as pntshp:

            for k, v in enumerate(newline):
                # print (k+1, v, v.length)
                km = km_s / 1000
                km_sta_f = "%.3f" % km
                km_sta_str = str(km_sta_f).replace(".", "+")
                pnt = v.interpolate(0.0, normalized=True)  # start Potree Viwer
                # print (km_sta_str)
                try:
                    pntshp.write({
                        'geometry': mapping(pnt),
                        'properties': {'section_part_id': k + 1, 'km_m': km_sta_str}
                    })
                    k = k + 1
                    km_s = km_s + self.DISTm
                except:
                    logging.exception("Error processing feature %s:", k)
            # Close
            pntshp.closed

rawshp = int(input('ระยะทางทั้งหมด ='))
rawbuf = int(input('ขนาดความกว้าง buffer ='))
if __name__ == '__main__':
    # parser = argparse.ArgumentParser(description='Read SHP')
    # parser.add_argument('-i', help='Dir KML Folder name')
    # args = parser.parse_args()

    # if args.i is None:
    #    parser.print_help()
    #    sys.exit()
    # if os.path.exists(args.i) == True:
    #    indir = args.i
    #    read_dir(indir)

    CLASSSHP = RawShapefile(rawshp, rawbuf)
    CLASSSHP.process()
count_section = len(newline)
print('Clip_buffer_form_centerline : sucessfully')

print('waiting for Exportsection.........')
#-------------------------------------------------------------------------------------------------------
path = '%s\clip_buffer_output\%s_1_clip_buff.shp' %(path_in,f_n)
world = gpd.read_file(path)
output_path = '%s\clip_buffer_output\export_section' %(path_in)
count_section = len(newline)
selection = world[0:count_section].reset_index(drop=True)

for row in selection.index:
  #print(selection['name_left'][row], selection['geometry'][row])
  gdf = gpd.GeoDataFrame(selection[row:row+1], crs='EPSG:32647')
  gdf.to_file(driver='ESRI Shapefile', filename=output_path+"\\section_"+str(selection['section_pa'][row]))

print('Export_section : sucessfully')
# #-------------------------------------------------------------------------------------------------------


print('waiting for Clip_LAS.........')
for i in range(count_section):
    if i < count_section - 1:
        km_end = k_start + (1000 * (int(i+1)))
        km_str = km_end - 1000
    else:
        km_str = k_start + (1000 * (count_section - 1))
        km_end = k_end
    #print("D:\\install\\WBT\\whitebox_tools.exe -r=ClipLidarToPolygon -i D:\\infraplus\\HRIS\\survey_data\\DEMO\\A_to_GIS\\pointcloud\\20210219_338_31780100a.las --polygon D:\\infraplus\\HRIS\\survey_data\\DEMO\\A_to_GIS\\cl\\buffer\\section_%s\\section_%s.shp -o D:\\infraplus\\HRIS\\survey_data\\DEMO\A_to_GIS\\pointcloud\\output\\20210219_338_31780100a_%s+%s.las" %(i+1,i+1,km_str,km_end))
    dir_lb5 = os.path.join(r'D:\\install\\WBT\\whitebox_tools.exe')
    subprocess.call(r"D:\install\WBT\whitebox_tools.exe -r=ClipLidarToPolygon -i %s\%s.las --polygon %s\clip_buffer_output\export_section\section_%s\section_%s.shp -o %s\clip_pointcloud_output\%s_%s_to_%s.las" %(path_in,f_n,path_in,i+1,i+1,path_in,f_n,km_str,km_end))
    print('Clipsection :', (i+1),'finish')
print('Clip_LAS : sucessfully')
#-------------------------------------------------------------------------------------------------------
print('waiting for Converter_potree.........')
for i in range(count_section) :
    if i < count_section - 1:
        km_end = k_start + (1000 * (int(i + 1)))
        km_str = km_end - 1000
    else:
        km_str = k_start + (1000 * (count_section - 1))
        km_end = k_end
    #dir_potree = os.path.join(r'D:\\infraplus\\HRIS\\PotreeConverter_2.0.2\\PotreeConverter.exe')
    subprocess.call(
        r'D:\infraplus\HRIS\PotreeConverter_2.0.2\PotreeConverter.exe -i "%s\clip_pointcloud_output\%s_%s_to_%s.las" -o %s\%s\%s_%s_to_%s' % (path_in, f_n, km_str, km_end, path_in, f_n, f_n, km_str, km_end))
    print('Converter_Potree :', (i + 1))
print('Converter_Potree : sucessfully')
# #-------------------------------------------------------------------------------------------------------
