"""
Summary type queries for getting totals from the triplestore
"""
CLASS_COUNTS = """
# Summary counts of bf:Work, bf:Instance and bf:Item
prefix bf: <http://id.loc.gov/ontologies/bibframe/>
Select ?Type ?Item_Count
{
    {
        {
            SELECT ?Type ?order (count(?type) as ?Item_Count)
            {
                {
                    SELECT DISTINCT ?type
                    {
                        VALUES ?types {
                            bf:Audio
                            bf:Cartography
                            bf:Dataset
                            bf:MixedMaterial
                            bf:MovingImage
                            bf:Multimedia
                            bf:NotatedMovement
                            bf:NotatedMusic
                            bf:Object
                            bf:StillImage
                            bf:Text
                            bf:Work
                        }
                        ?type a ?types .
                     }
                }

                bind("Works" as ?Type)
                bind(1 as ?order)
            }
            group by ?Type ?order
        }
    } UNION {
        {
            SELECT ?Type ?order (count(?type) as ?Item_Count)
            {
                {
                    SELECT DISTINCT ?type
                    {
                        VALUES ?types {
                            bf:Archival
                            bf:Electronic
                            bf:Manuscript
                            bf:Print
                            bf:Tactile
                            bf:Instance
                        }
                        ?type a ?types .
                     }
                }

                bind("Instances" as ?Type)
                bind(2 as ?order)
            }
            group by ?Type ?order
        }
    } UNION {
        {
            SELECT ?Type ?order (count(?type) as ?Item_Count)
            {
                ?type a bf:Item .
                bind("Items" as ?Type)
                bind(3 as ?order)
            }
            group by ?Type ?order
        }
    }
}
order by ?order
"""

"""
# Counts of bf:Work with a count of tied bf:Instance
prefix bf: <http://id.loc.gov/ontologies/bibframe/>
SELECT *
{
{
Select ?work (count(?instance) as ?tied_count)
{
  ?instance bf:instanceOf ?work
}
group by ?work
}
FILTER(?tied_count>1)
}
order by DESC(?tied_count)
"""
