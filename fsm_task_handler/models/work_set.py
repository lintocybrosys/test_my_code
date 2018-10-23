import logging

from odoo import api, exceptions, fields, models, _

_logger = logging.getLogger(__name__)


class WorksetTeamRelation(models.Model):
    _name = 'workset.fsm.teams'

    workset_id = fields.Many2one('fsm.work_set',
                                 string="Workset")
    team_id = fields.Many2one('fsm.teams',
                              string="Team")


class WorkSetsFSM(models.Model):
    _name = 'fsm.work_set'
    _inherit = 'mail.thread'
    _description = 'Work-set'

    # making the name, unique
    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Work-Set name already exists !"),
    ]

    def _default_stage_set(self):
        """Setting default stage"""
        rec = self.env['fsm.stage.sets'].search([], limit=1)
        return rec.id if rec else None

    @api.one
    def _default_stage_id(self):
        """This function will be executed each time we load the form,
        so we are setting the current stage after checking
        the field, next_stage, which will be set
         after clicking the next_stage button or reset button."""
        if self.stage_set.stage_ids:
            temp_stage_set = \
                self.stage_set.stage_ids.sorted(key=lambda r: r.sequence)[0]
            stage = temp_stage_set.stage_id \
                if not self.stage_id else self.stage_id

            if not self.next_stage:
                self.stage_id = stage.id if stage else None
            else:
                self.stage_id = self.next_stage.id
            self.previous_stage = None
            self.upcoming_stage = None
            for i in range(0, len(self.stage_set.stage_ids)):
                stage = \
                    self.stage_set.stage_ids.sorted(key=lambda r: r.sequence)
                if stage[i].stage_id.id == self.stage_id.id:
                    self.previous_stage = \
                        stage[i-1].stage_id.name if i > 0 else None
                    self.upcoming_stage = \
                        stage[i+1].stage_id.name if i+1 < len(stage) else None
                    break

    name = fields.Char(string='Name',
                       required=True)
    work_order_id = fields.Many2one('fsm.order',
                                    string="Work-order")

    description = fields.Text(string='Description')

    work_set_forms = fields.One2many('work_set.form',
                                     'work_set_id',
                                     string="Questionnaires")
    work_set_answers = fields.One2many('work_set.answers',
                                       'work_set_id',
                                       string="Answers")
    price_categ = fields.Selection([('low', 'Low'),
                                    ('medium', 'Medium'),
                                    ('high', 'High')],
                                   string="Price Category")
    stage_set = fields.Many2one('fsm.stage.sets',
                                default=lambda self: self._default_stage_set(),
                                string="Stage Set",
                                required=True)
    stage_id = fields.Many2one('fsm.stages',
                               string='Stage',
                               index=True,
                               compute='_default_stage_id')
    previous_stage = fields.Char(string='Previous stage',
                                 compute='_default_stage_id')
    upcoming_stage = fields.Char(string='Upcoming stage',
                                 compute='_default_stage_id')
    color = fields.Integer('Color Index',
                           default=0)
    next_stage = fields.Many2one('fsm.stages',
                                 string="Status",
                                 track_visibility='onchange')
    state = fields.Char(string="State")
    team_id = fields.One2many('workset.fsm.teams',
                              'workset_id',
                              string="Teams")
    customer_id = fields.Many2one('res.partner',
                                  domain="[('customer', '=', True)]",
                                  string="Customer",
                                  related='work_order_id.customer_id',
                                  track_visibility='onchange')
    question_categ = fields.One2many('question.category',
                                     'work_set_id')
    reject_reason = fields.Text(string="Reason",
                                help="Provide a short note"
                                     " on proposal rejection",
                                track_visibility='onchange')
    # a flag to specify the work order status, whether it is started or not
    work_started_flag = fields.Char(string="Work Started",
                                    default="False")

    @api.multi
    def write(self, vals):
        """
        This is where we are creating the
        questions related to the selected surveys.
        This will be executed when we modify
        an existing record.
        """
        res = super(WorkSetsFSM, self).write(vals)
        if vals.get('work_set_forms'):
            for rec in vals.get('work_set_forms'):
                if rec[2]:
                    survey_id = rec[2].get('name')
                    for question in\
                            self.env['product.survey'].browse(survey_id):
                        self.write({
                            'work_set_answers': [(0, 0, {
                                'name': question.name,
                                'work_set_id': self.id,
                                'survey_id': survey_id
                            })]
                        })
        return res

    @api.model
    def create(self, vals):
        """
        We are setting the questions for
        the related surveys here. This will be executed when we
        create new records.
        """
        res = super(WorkSetsFSM, self).create(vals)
        if vals.get('work_set_forms'):
            for rec in vals.get('work_set_forms'):
                if rec[2]:
                    survey_id = rec[2].get('name')
                    for question in\
                            self.env['product.survey'].browse(survey_id):
                        res.write({
                            'work_set_answers': [(0, 0, {
                                'name': question.name,
                                'work_set_id': self.id,
                                'survey_id': survey_id
                            })]
                        })
        return res

    @api.model
    def action_open_worksets(self):
        """Opens the work-sets based on the signed in user"""
        user = self.env.user
        cr = self._cr
        person_obj = self.env['fsm.person']
        # here the employees refers to the person who are assigned the job
        employees = \
            person_obj.search([('partner_id', '=', user.partner_id.id)]) or []
        if user.id == 1:
            # admin should see all the records
            # setting domain to empty
            domain = []
        else:
            # the signed in user is not admin
            # so we need to check his privileages
            if user.has_group('fieldservice.group_fsm_manager'):
                # this user is a manager
                # selecting all the items

                domain = []

            elif employees and \
                    user.has_group('fieldservice.group_fsm_dispatcher'):
                # case: team leader
                # selecting the teams where
                # this employee/person is the leader or member
                if user.fsm_team_ids:
                    teams = user.fsm_team_ids.ids
                else:
                    teams = []

                ids = []
                if teams:
                    cr.execute("SELECT workset_id "
                               "FROM workset_fsm_teams "
                               " WHERE team_id IN %s", (tuple(teams), ))
                    ids = [i[0] for i in cr.fetchall()]

                domain = "[('id', 'in', " + str(ids) + ")]"
            elif employees and user.has_group('fieldservice.group_fsm_user'):
                # case: employee
                # selecting all the teams this employee is member of
                teams = []
                for team in user.fsm_team_ids:
                    for j in team.team_members:
                        if j.name.id in employees.ids:
                            teams.append(team.id) if\
                                team.id not in teams else None
                ids = []
                if teams:
                    cr.execute("SELECT workset_id "
                               "FROM workset_fsm_teams "
                               "WHERE team_id IN %s",
                               (tuple(teams),))
                    ids = [i[0] for i in cr.fetchall()]

                domain = "[('id', 'in', " + str(ids) + ")]"
            elif not employees:
                domain = "[('id', 'in', " + str([]) + ")]"
        return {
            'name': 'Work-Sets',
            'type': 'ir.actions.act_window',
            'res_model': 'fsm.work_set',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'tree_view_ref': 'fsm_task_handler.fsm_work_sets_tree',
                'form_view_ref': 'fsm_task_handler.fsm_work_sets_form',
            }
        }

    def approve_operation(self):
        """Approves the proposal assigned to the person"""
        stage_id = self.env['fsm.stages'].search([('name', '=', 'Approved')],
                                                 limit=1)
        if not stage_id:
            stage_id = self.env['fsm.stages'].create({'name': 'Approved'})
        self.next_stage = stage_id.id
        self.state = stage_id.name
        return False

    def reject_operation(self):
        """Rejects the proposal assigned to the person"""
        stage_id = self.env['fsm.stages'].search([('name', '=', 'Rejected')],
                                                 limit=1)
        if not stage_id:
            stage_id = self.env['fsm.stages'].create({'name': 'Rejected'})
        self.next_stage = stage_id.id
        self.state = stage_id.name
        return False

    @api.multi
    def reset_to_initial_stage(self):
        """This method will set the current record to the
        initial stage of the stage set associated with it."""
        for workset in self:
            if workset.stage_set and workset.stage_set.stage_ids:
                workset.work_started_flag = "False"
                # sorting stages by sequence
                stage_ids = workset.stage_set.stage_ids
                stages = stage_ids.sorted(key=lambda r: r.sequence)
                workset.next_stage = stages[0].stage_id.id
                workset.state = stages[0].stage_id.name
                # resetting the stages of child workitems, if there are any
            else:
                raise exceptions.UserError(_('Please check stage set !'))

    def proceed_to_next_stage(self):
        """Proceed to the next stage after checking the
        conditions if any."""
        # sorting the stages
        stages = \
            self.stage_set.stage_ids.sorted(key=lambda r: r.sequence)

        # finding  next stage
        results = \
            self.find_next_stage(self.stage_id, stages)
        next_stage = results[1]

        if next_stage:
            self.next_stage = next_stage.stage_id.id
            self.state = next_stage.stage_id.name

    def find_next_stage(self, current_stage, stages):
        """
        Finds next stage which the record should go to.
        :param current_stage: current stage of the record
        :param stages: recordset of stages associated with
        the selected stage set, sorted by sequence
        :return: current stage and next stage from
         the stage set provided
        """
        res = []

        for i in range(0, len(stages)):
            if stages[i].stage_id.name == current_stage.name:
                res.append(stages[i])
                if i+1 <= len(stages) - 1:
                    res.append(stages[i + 1])

                    return res
                else:
                    raise exceptions.UserError(_('This is the '
                                                 'final stage !'))
        return res
