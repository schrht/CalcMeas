#!/usr/bin/env python

'''
Owner:      SHI, Chen
E-mail:     chen.shi@alcatel-lucent.com

History:
            v0.1    2016-03-07    SHI, Chen    init version
            v0.2    2016-03-08    SHI, Chen    demo version, calculate EPAY KPIs
            v0.3    2016-03-08    SHI, Chen    refactory the code, use 'dict' as element for infolists
            v0.3.1  2016-03-29    SHI, Chen    fix the "div 0" issue

'''

import sys
import re


role_define_list = {'pilot' : ('0-0-1', '0-0-9'),
                    'db1' : ('0-0-2', '0-0-10'),    # 'db1' for DB nodes with ACM 
                    'db2' : ('0-0-3', '0-0-11', '0-1-2', '0-1-10', '0-1-3', '0-1-11'),
                    'io' : ('0-0-4', '0-0-12')
                    }


SA_SPAMEAS_infolist = []
MS_PROCESS_MEAS_infolist = []



def get_block_info(measlog, num):
    '''this function receives measlog content and the current offset, return:
    1. (begin, end) offsets of the message block. format: (int, int)
    2. the report time of the message block. format: 'YYYY-MM-DD hh:mm'
    3*. the message id of the message block.
    *: not implemented. 
    '''
    
    # get (begin, end) offsets    
    begin = end = num
    while re.search(r'\+\+\+', measlog[begin]) is None:
        begin -= 1
    while re.search(r'\+\+\-', measlog[end]) is None:
        end += 1

    # get report time
    match_result = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', measlog[begin])
    if match_result:
        report_time = match_result.group(1)
    else:
        print 'Error: Failed to get report time of the message block.'
        report_time = '1970-01-01 12:00'

    return (begin, end, report_time)


def analyze_measlog(measlog):
    '''this function receives the measlog content, analyze the following tables:
    1. SA_SPAMEAS
    2. MS_PROCESS_MEAS
    and save the useful information in the lists respectively.
    '''
    
    num = 0
    while num < len(measlog):
        
        # analyze SA_SPAMEAS table
        if re.search(r'Measurements for SA_SPAMEAS table', measlog[num]) is not None:

            # get the information of current block
            begin, end, report_time = get_block_info(measlog, num)

            # get useful information
            num = begin
            while num < end:
                match_result = re.search(r'(\d+)\s+(\S+)\s+(\d+)\s+\d+', measlog[num])
                if match_result:
                    SA_SPAMEAS_info = {}
                    SA_SPAMEAS_info['tps'] = int(match_result.group(3)) / int(match_result.group(1)) 
                    SA_SPAMEAS_info['spa_name'] =  match_result.group(2)
                    SA_SPAMEAS_info['report_time'] = report_time
                    
                    # save the information
                    SA_SPAMEAS_infolist.append(SA_SPAMEAS_info)
                
                num += 1
            else:
                print 'Finished processing [', report_time, '] SA_SPAMEAS table;'
        
        # analyze MS_PROCESS_MEAS table
        if re.search(r'Measurements for MS_PROCESS_MEAS table', measlog[num]) is not None:

            # get the information of current block
            begin, end, report_time = get_block_info(measlog, num)

            # get useful information
            num = begin
            while num < end:
                #299  0-0-9   DIAMCL28I_2                     18.89
                match_result = re.search(r'\d+\s+(\d+-\d+-\d+)\s+(\S+)\s+(\d+\.\d+)', measlog[num])
                if match_result:
                    MS_PROCESS_MEAS_info = {}
                    MS_PROCESS_MEAS_info['host_id'] = match_result.group(1)
                    MS_PROCESS_MEAS_info['process_name'] = match_result.group(2)
                    MS_PROCESS_MEAS_info['cpu_usage'] = match_result.group(3)
                    MS_PROCESS_MEAS_info['report_time'] = report_time
                    
                    # save the information
                    MS_PROCESS_MEAS_infolist.append(MS_PROCESS_MEAS_info)
                
                num += 1
            else:
                print 'Finished processing [', report_time, '] MS_PROCESS_MEAS table;'
        
        
        # increase line number
        num += 1


    #print SA_SPAMEAS_infolist
    #print MS_PROCESS_MEAS_infolist

    return



def generate_reports():
    '''this function reads information from infolist then calculate the KPIs and print the report.''' 
    
    # generate EPAY KPIs report
    spa_name = ''
    epay_kpi_list = []
    
    # build epay_kpi_list from SA_SPAMEAS_infolist
    for item in SA_SPAMEAS_infolist:
        if item['spa_name'].find('EPAY') == 0:
            spa_name = item['spa_name']
            epay_kpi = {}
            epay_kpi['report_time'] = item['report_time']
            epay_kpi['tps'] = item['tps']
            epay_kpi_list.append(epay_kpi)
    
    
    # add more KPIs to epay_kpi_list from MS_PROCESS_MEAS_infolist
    for epay_kpi in epay_kpi_list:
        
        std_client_num = std_client_cpu_usage = 0
        spc_client_num = spc_client_cpu_usage = 0
        for item in MS_PROCESS_MEAS_infolist:
            
            # calculate standard client average CPU usage
            if item['report_time'] == epay_kpi['report_time'] and \
            item['host_id'] not in role_define_list['db1'] and \
            item['process_name'].find(spa_name + '_') == 0:
                std_client_num += 1
                std_client_cpu_usage += float(item['cpu_usage'])
 
            # calculate specialized client average CPU usage
            if item['report_time'] == epay_kpi['report_time'] and \
            item['host_id'] in role_define_list['db1'] and \
            item['process_name'].find(spa_name + '_') == 0:
                spc_client_num += 1
                spc_client_cpu_usage += float(item['cpu_usage'])
            
        # calculate and save the KPIs
        epay_kpi['std_client_num'] = std_client_num
        if std_client_num:
            epay_kpi['std_client_cpu_usage'] = std_client_cpu_usage / std_client_num
            epay_kpi['std_client_call_cost'] = epay_kpi['std_client_cpu_usage'] * 10 * epay_kpi['std_client_num'] / epay_kpi['tps']
        else:
            epay_kpi['std_client_cpu_usage'] = 0
            epay_kpi['std_client_call_cost'] = 0
        
        epay_kpi['spc_client_num'] = spc_client_num
        if spc_client_num:
            epay_kpi['spc_client_cpu_usage'] = spc_client_cpu_usage / spc_client_num
            epay_kpi['spc_client_call_cost'] = epay_kpi['spc_client_cpu_usage'] * 10 * epay_kpi['spc_client_num'] / epay_kpi['tps']
        else:
            epay_kpi['spc_client_cpu_usage'] = 0
            epay_kpi['spc_client_call_cost'] = 0

    # calculate the final line
    count = 0
    average_tps = 0
    average_std_client_cpu_usage = average_std_client_call_cost = 0
    average_spc_client_cpu_usage = average_spc_client_call_cost = 0
    
    for item in epay_kpi_list:
        count += 1
        average_tps += item['tps']
        average_std_client_cpu_usage += item['std_client_cpu_usage']
        average_std_client_call_cost += item['std_client_call_cost']
        average_spc_client_cpu_usage += item['spc_client_cpu_usage']    
        average_spc_client_call_cost += item['spc_client_call_cost']
    
    if count:   
        average_tps /= count
        average_std_client_cpu_usage /= count
        average_std_client_call_cost /= count
        average_spc_client_cpu_usage /= count
        average_spc_client_call_cost /= count
    else:
        average_tps = 0
        average_std_client_cpu_usage = 0
        average_std_client_call_cost = 0
        average_spc_client_cpu_usage = 0
        average_spc_client_call_cost = 0
        
    # print out the report
    print '\nEPAY SPA KPI report: (demo version)'
    print '=' * 60
    print '# report_time, tps, StdClient# CPU% CallCost, SpcClient# CPU% CallCost'
    
    count = 0
    for item in epay_kpi_list:
        count += 1
        print count, item['report_time'], format(item['tps'], ','), \
        item['std_client_num'], format(item['std_client_cpu_usage'], '.2f'), format(item['std_client_call_cost'], '.2f'), \
        item['spc_client_num'], format(item['spc_client_cpu_usage'], '.2f'), format(item['spc_client_call_cost'], '.2f')
    print '-' * 60
    print '  AVERAGE         ', format(average_tps, ','), \
    '--', format(average_std_client_cpu_usage, '.2f'), format(average_std_client_call_cost, '.2f'), \
    '-', format(average_spc_client_cpu_usage, '.2f'), format(average_spc_client_call_cost, '.2f')
    return


def main():
    '''check input parameters, load the meanslog file'''
    
    if len(sys.argv) < 2:
        print 'Usage: calcmeas.py <measlog file>'
        return
    else:
        print "Measurement log file: ", sys.argv[1]
        
        # read measlog file
        f = open(sys.argv[1], 'r')
        measlog = f.readlines()
        f.close()

    analyze_measlog(measlog)
    generate_reports()
    
    
    print '=' * 60
    print 'finished!'
    
    return


if __name__ == '__main__':
    main()
