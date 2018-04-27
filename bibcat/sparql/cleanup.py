"""
SPARQL queries used to clean up datasets
"""
DELETE_MULTIPLE_ITEMOF = """
# DELETE_MULTIPLE_ITEMOF
# Deletes multiple bf:itemOf triples if there is more than one associated
# bf:Instance for a bf:Item picking the bf:Instance with the most triples
prefix bf: <http://id.loc.gov/ontologies/bibframe/>
DELETE
{
  ?item bf:itemOf ?del_instance .
}
WHERE
{
    SELECT  ?del_instance ?item
    {
        {
            # Merge and count all of the
            SELECT ?item
                   (count(?instance) as ?item_count)
                   (GROUP_CONCAT(str(?instance); separator="|") as ?instances)
            {
                # Retrieve all of the  bf:Instance and bf:Item links selecting
                # the bf:Instanct with the most triples
                SELECT ?item ?instance ?hasWork (count(?p) as ?triple_count)
                {
                    ?item bf:itemOf ?instance.
                    ?instance ?p ?o .
                    optional {
                      ?instance bf:instanceOf ?work
                    }
                    BIND(bound(?work) as ?hasWork)
                }
                group by ?item ?instance ?hasWork
                order by DESC(?hasWork) DESC(?triple_count)
            }
            group by ?item
        }
        FILTER (?item_count>1)
        ?item bf:itemOf ?new_instance .
        BIND (IRI(?new_instance) as ?del_instance) .
        BIND(IRI(STRBEFORE(?instances, "|")) as ?save_instance ).
        FILTER (?del_instance!=?save_instance) .
    }
    order by ?del_instance
}
"""

DELETE_ORPHAN_INSTANCES = """
# DELETE_ORPHAN_INSTANCES
# DELETE orphan bf:Instance

prefix bf: <http://id.loc.gov/ontologies/bibframe/>
DELETE
{
    ?instance ?p ?o .
    ?bns ?bnp ?bno .
}
WHERE
{
    # Get all of the instances not tied to an item
    {
        ?instance a bf:Instance .
        optional {
            ?item bf:itemOf ?instance
        }
        filter(!(bound(?item)))
    }
    ?instance ?p ?o .

    # Get all of the associated blank nodes
    optional {
        ?o ?bnp ?bno .
        filter(isblank(?o))
        bind(?o as ?bns)
    } .
}
"""

CREATE_MISSING_WORKS = """
# CREATE_MISSING_WORKS
# creates a bf:Work IRI and rdf:type association for a bf:Instance that is
# missing an associated work

prefix bf: <http://id.loc.gov/ontologies/bibframe/>
INSERT
{
    ?instance bf:instanceOf ?new_work .
    ?new_work a bf:Work .
}
WHERE
{
    ?instance a bf:Instance
    optional {
        ?instance bf:instanceOf ?work
    }
    bind(IRI(CONCAT(STR(?instance), "#Work")) as ?new_work)
    FILTER(!(bound(?work)))
}
"""

DELETE_ORPHAN_WORKS = """
# DELETE_ORPHAN_WORKS
# DELETE all orphan bf:Work triples

prefix bf: <http://id.loc.gov/ontologies/bibframe/>
DELETE
{
    ?work ?p ?o .
    ?bns ?bnp ?bno .
}
WHERE
{
    # Get all of the works not tied to an instance
    {
        ?work a bf:Work .
        optional {
            ?instance bf:instanceOf ?work .
        }
        filter(!(bound(?instance)))
    }
    ?work ?p ?o .

    # Get all of the associated blank nodes
    optional {
        ?o ?bnp ?bno .
        filter(isblank(?o))
        bind(?o as ?bns)
    } .
}
"""

DELETE_INSTANCE_LINKS_MISSING_TITLES = """
# DELETE_INSTANCE_LINKS_MISSING_TITLES
# Deletes bf:Instance linkages to works and items when the bf:Instance does
# NOT have bf:title property

prefix bf: <http://id.loc.gov/ontologies/bibframe/>
DELETE {
  ?instance bf:instanceOf ?work.
  ?item bf:itemOf ?instance .
}
WHERE
{
    {
        ?instance a bf:Instance .
        optional {
            ?instance bf:title ?title
        }
        filter(!(bound(?title)))
    }
    ?instance bf:instanceOf ?work .
    ?item bf:itemOf ?instance .
}
"""

DELETE_ORPHAN_ITEMS = """
# DELETE_ORPHAN_ITEMS
# DELETE all orphan bf:Item triples that are not linked to a bf:Instance

prefix bf: <http://id.loc.gov/ontologies/bibframe/>
DELETE
{
    ?item ?p ?o .
    ?bns ?bnp ?bno .
}
WHERE
{
    # Get all of the items not tied to an instance
    {
        ?item a bf:Item .
        optional {
            ?item bf:itemOf ?instance .
        }
        filter(!(bound(?instance)))
    }
    ?item ?p ?o .

    # Get all of the associated blank nodes
    optional {
        ?o ?bnp ?bno .
        filter(isblank(?o))
        bind(?o as ?bns)
    } .
}
"""

DELETE_MULTIPLE_GEN_PROCESS = """
# DELETE_MULTIPLE_GEN_PROCESS
# Deletes all but one bf:generationProccess when attached to a subject

prefix bf: <http://id.loc.gov/ontologies/bibframe/>

DELETE
{
    ?item bf:generationProcess ?new_policy .
    ?bns ?bnp ?bno.
}
WHERE
{
    {
        SELECT ?item  (MIN(?policy) as ?keep) (count(?policy) as ?p_count)
        {
            ?item bf:generationProcess ?policy .
        }
        group by ?item
    }
    filter(?p_count>1)
    ?item bf:generationProcess ?new_policy .
    filter(?keep!=?new_policy) .
    bind(?new_policy as ?bns) .
    optional {
        ?bns ?bnp ?bno .
    } .
}
"""
CLEANUP_QRY_SERIES = [DELETE_MULTIPLE_ITEMOF,
                      DELETE_ORPHAN_INSTANCES,
                      CREATE_MISSING_WORKS,
                      DELETE_ORPHAN_WORKS,
                      DELETE_MULTIPLE_GEN_PROCESS]


CLEANUP_MISSING_TITLE_SERIES = [DELETE_INSTANCE_LINKS_MISSING_TITLES,
                                DELETE_ORPHAN_INSTANCES,
                                DELETE_ORPHAN_WORKS,
                                DELETE_ORPHAN_ITEMS]
