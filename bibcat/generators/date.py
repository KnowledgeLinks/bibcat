"""Date Generator class a stop-gap until rdfframework date utilities are ready"""
__author__ = "Jeremy Nelson"

import datetime
import re

class DateGenerator(object):

    def __init__(self, **kwargs):
        pass


    def add_range(self, start, end):
        for date_row in range(int(start), int(end)+1):
            self.add_year(date_row)

    
    def add_4_years(self, result):
             graph.add((work, BF.temporalCoverage, rdflib.Literal(raw_date)))
             start, end = result.groups()
             add_range(start, end)
     def add_4_to_2_years(result):
             start_year, stub_year = result.groups()
             end_year = "{}{}".format(start_year[0:2], stub_year)
             graph.add((work, BF.temporalCoverage, rdflib.Literal("{} to {}".format(start_year, end_year))))
             add_range(start_year, end_year)
     def add_year(year):
             bnode = rdflib.BNode()
             graph.add((work, BF.subject, bnode))
             graph.add((bnode, rdflib.RDF.type, BF.Temporal))
             graph.add((bnode, rdflib.RDF.value, rdflib.Literal(year)))
	raw_date = row.get("Dates.Date Range")
	if len(raw_date) == 4:
		add_year(raw_date)
	result = RANGE_4YEARS.search(raw_date)
	if result is not None:
		add_4_years(result)
	result = RANGE_4to2YEARS.search(raw_date)
	if result is not None:
		add_4_to_2_years(result)
	if "," in raw_date:
		for comma_row in raw_date.split(","):
			pass
