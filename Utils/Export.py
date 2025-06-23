import xml.etree.ElementTree as ET
from xml.dom import minidom

def patients_to_xml(patients):
    root = ET.Element("Patients")
    for patient in patients:
        p_elem = ET.SubElement(root, "Patient")
        for key, value in patient.items():
            if key == "tests":
                tests_elem = ET.SubElement(p_elem, "Tests")
                for test in value:
                    test_elem = ET.SubElement(tests_elem, "Test")
                    for tk, tv in test.items():
                        ET.SubElement(test_elem, tk).text = str(tv)
            else:
                ET.SubElement(p_elem, key).text = str(value)

    # Convert to a string and pretty print
    rough_string = ET.tostring(root, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    return pretty_xml
