{
    'name': "Field Service Teams",
    'summary': """Teams for handling the jobs.""",
    'description': """Jobs can be assigned to a team.
    Members of the team will be handling the work.""",
    'author': "redO2oo.ch2",
    'website': "https://www.redo2oo.ch",
    'category': 'Field Service',
    'version': '11.0.1.0.0',
    'depends': [
        'base',
        'web_tour',
        'fieldservice',
        'fsm_base'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/skill_view.xml',
        'views/fsm_person_extended.xml'
    ],
    'demo': [],
}