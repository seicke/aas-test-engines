from unittest import TestCase
import os
import zipfile
import io
import json
from xml.etree import ElementTree

from aas_test_engines import file, exception

script_dir = os.path.dirname(os.path.realpath(__file__))


def in_memory_zipfile(path: str):
    buffer = io.BytesIO()
    zip = zipfile.ZipFile(buffer, "a", zipfile.ZIP_DEFLATED, False)
    for root, subdirs, files in os.walk(path):
        for file in files:
            real_path = os.path.join(root, file)
            archive_path = real_path[len(path)+1:]
            zip.write(real_path, archive_path)
    return zip


class CheckJsonTest(TestCase):

    def test_empty(self):
        result = file.check_json_data({})
        self.assertTrue(result.ok())

    def test_no_json(self):
        result = file.check_json_file(io.StringIO("no json"))
        self.assertFalse(result.ok())


class CheckXmlTest(TestCase):

    def test_empty(self):
        data = ElementTree.fromstring(
            """<environment xmlns="https://admin-shell.io/aas/3/0">
            </environment>""")
        result = file.check_xml_data(data)
        self.assertTrue(result.ok())

    def test_invalid_namespace(self):
        data = ElementTree.fromstring(
            """<environment xmlns="invalid">
            </environment>""")
        result = file.check_xml_data(data)
        self.assertFalse(result.ok())
        result.dump()

    def test_no_xml(self):
        result = file.check_xml_file(io.StringIO("no xml"))
        self.assertFalse(result.ok())


class CheckAasxTest(TestCase):

    def test_not_a_zip(self):
        with open(os.path.join(script_dir, 'fixtures/aasx/invalid/invalid_json/[Content_Types].xml'), "rb") as f:
            result = file.check_aasx_file(f)
        result.dump()
        self.assertFalse(result.ok())

    def test_empty(self):
        z = in_memory_zipfile(os.path.join(
            script_dir, 'fixtures/aasx/invalid/empty'))
        result = file.check_aasx_data(z)
        result.dump()
        self.assertFalse(result.ok())

    def test_no_rels(self):
        z = in_memory_zipfile(os.path.join(
            script_dir, 'fixtures/aasx/invalid/no_rels'))
        result = file.check_aasx_data(z)
        result.dump()
        self.assertFalse(result.ok())

    def test_invalid_rels(self):
        z = in_memory_zipfile(os.path.join(
            script_dir, 'fixtures/aasx/invalid/invalid_rels'))
        result = file.check_aasx_data(z)
        result.dump()
        self.assertFalse(result.ok())

    def test_unknown_filetype(self):
        z = in_memory_zipfile(os.path.join(
            script_dir, 'fixtures/aasx/invalid/unknown_filetype'))
        result = file.check_aasx_data(z)
        result.dump()
        self.assertFalse(result.ok())

    def test_valid_xml(self):
        z = in_memory_zipfile(os.path.join(script_dir, 'fixtures/aasx/valid/xml'))
        result = file.check_aasx_data(z)
        result.dump()
        self.assertTrue(result.ok())

    def test_valid_json(self):
        z = in_memory_zipfile(os.path.join(script_dir, 'fixtures/aasx/valid/json'))
        result = file.check_aasx_data(z)
        result.dump()
        self.assertTrue(result.ok())

    def test_invalid_xml(self):
        z = in_memory_zipfile(os.path.join(script_dir, 'fixtures/aasx/invalid/invalid_xml'))
        result = file.check_aasx_data(z)
        result.dump()
        self.assertFalse(result.ok())

    def test_invalid_json(self):
        z = in_memory_zipfile(os.path.join(script_dir, 'fixtures/aasx/invalid/invalid_json'))
        result = file.check_aasx_data(z)
        result.dump()
        self.assertFalse(result.ok())

    def test_relative_paths(self):
        z = in_memory_zipfile(os.path.join(script_dir, 'fixtures/aasx/valid/relative_paths'))
        result = file.check_aasx_data(z)
        result.dump()
        self.assertTrue(result.ok())


class SupportedVersionTest(TestCase):

    def test_invoke(self):
        s = file.supported_versions()
        for version, templates in s.items():
            print(f"{version}: {', '.join(templates)}")
        self.assertIn(file.latest_version(), s)


class GenerateTest(TestCase):

    def check(self, generator):
        i = 0
        for _ in generator:
            i += 1
            if i > 10:
                break

    def test_meta_model(self):
        generator = file.generate()
        self.check(generator)

    def test_generate_contact_info(self):
        generator = file.generate(submodel_template='ContactInformation')
        self.check(generator)

    def test_invalid_name(self):
        with self.assertRaises(exception.AasTestToolsException):
            generator = file.generate(submodel_template="xyz")
            self.check(generator)


class CheckSubmodelTemplate(TestCase):

    def test_contact_info(self):
        templates = set(['ContactInformation'])
        with open(os.path.join(script_dir, 'fixtures', 'submodel_templates', 'contact_information.json')) as f:
            data = json.load(f)
        result = file.check_json_data(data, submodel_templates=templates)
        result.dump()
        self.assertTrue(result.ok())
        data['submodels'][0]['submodelElements'][0]['value'][0]['value'] = 'invalid'
        result = file.check_json_data(data, submodel_templates=templates)
        result.dump()
        self.assertFalse(result.ok())

    def test_no_submodels(self):
        data = {}
        # is compliant to meta-model...
        result = file.check_json_data(data)
        self.assertTrue(result.ok())
        # ...but does not contain any submodels
        result = file.check_json_data(data, submodel_templates=set(['ContactInformation']))
        result.dump()
        self.assertFalse(result.ok())
