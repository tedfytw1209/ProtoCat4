from django.shortcuts import *
from django.http import *
from .models import *
from django.contrib.auth import *
from django.db.models import Q
from django.db import connection
import datetime
from django.utils import timezone
from django.core.files import File
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.db.models import Max
from django.views.generic import View, FormView
from . import forms, models
import bleach
from protocat.converter.Converter import converter
import json

def index(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)

		messages = models.Message.objects.filter(recipient = current_profile_info).filter(read = False).filter(deleted = False)

	else:
		current_profile_info = None
		messages = [];
	context = {
		'title': 'ProtoCat4.0',
		'current_profile_info': current_profile_info,
		'numMessages': len(messages),
	}
	return render(request, 'index.html', context)

def category_default(request):
	current_parent = None
	return category_browser(request, current_parent)

def category_specific(request, category_id):
	current_parent = Category.objects.get(id = category_id)
	return category_browser(request, current_parent)

def category_browser(request, current_parent):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	categories = Category.objects.filter(parent_category = current_parent)
	protocols = Protocol.objects.filter(category = current_parent).filter(searchable = True)

	text = 'ProtoCat'
	context = {
		'title': 'ProtoCat - Browse Categories',
		'parent_category': current_parent,
		'categories': categories,
		'protocols': protocols,
		'current_profile_info': current_profile_info,
	}
	return render(request, 'category_browser.html', context)

def protocol(request, protocol_id):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	protocol = Protocol.objects.get(id = protocol_id)
	protocol_steps = ProtocolStep.objects.filter(protocol = protocol).order_by('step_number')
	protocol_reagents = ReagentForProtocol.objects.filter(protocol = protocol).order_by('display_name')
	next_protocols = Protocol.objects.filter(previous_revision = protocol)
	comments = ProtocolComment.objects.filter(protocol = protocol).order_by('-upload_date')

	# go through each reagent, get rid of duplicates
	aggregated_reagents = None
	if (protocol_reagents != None):
		aggregated_reagents = list(protocol_reagents[:1])
		for protocol_reagent in protocol_reagents:
			to_add = True
			for aggregated_reagent in aggregated_reagents:
				if (protocol_reagent.reagent_type == 1 and aggregated_reagent.reagent == protocol_reagent.reagent and aggregated_reagent.unit == protocol_reagent.unit):
					to_add = False
			if (to_add):
				aggregated_reagents.append(protocol_reagent)

	try:
		rating = ProtocolRating.objects.get(person = current_profile_info, protocol = protocol)
	except:
		rating = None

	if (current_profile_info == None):
		is_favorite = None
	else:
		is_favorite = current_profile_info.favorites.filter(id = protocol.id).exists()

	context = {
		'title': protocol.title,
		'protocol': protocol,
		'protocol_steps': protocol_steps,
		'protocol_reagents': protocol_reagents,
		'next_protocols': next_protocols,
		'comments': comments,
		'aggregated_reagents': aggregated_reagents,
		'user_rating': rating,
		'current_profile_info': current_profile_info,
		'is_favorite': is_favorite
	}

	return render(request, 'protocol.html', context)

def user(request, user_id):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None

	user = ProfileInfo.objects.get(id = user_id)
	user_created_protocols = Protocol.objects.filter(author = user).order_by('-upload_date')
	user_created_notes = ProtocolComment.objects.filter(author = user).order_by('-upload_date')
	user_rated_protocols = ProtocolRating.objects.filter(person = user).order_by('-score')

	title = 'ProtoCat - ' + str(user.user)

	context = {
		'title': title,
		'current_profile_info': current_profile_info,
		'profile_info': user,
		'user_created_protocols': user_created_protocols,
		'user_rated_protocols': user_rated_protocols,
		'notes': user_created_notes
	}

	# either allow user to edit or not
	if (current_profile_info != user):
		return render(request, 'user.html', context)
	else:
		return render(request, 'edit_user.html', context)

def sign_up(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	context = {
		'title': 'ProtoCat - Sign Up',
		'current_profile_info': current_profile_info,
	}
	return render(request, 'sign_up.html', context)

def submit_sign_up(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	try:
		# grab data to verify user
		username = request.POST['username']
		password = request.POST['password']
		email = request.POST['email']
		user = User.objects.create_user(username, email, password)
		user = authenticate(username = username, password = password)
		profile_info = ProfileInfo(user = user)
		profile_info.save()
		current_profile_info = profile_info
		login(request, user)
		return JsonResponse({'success': True, 'location': '/'})
	except:
		return JsonResponse({'success': False})

def login_user(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	context = {
		'title': 'ProtoCat - Login',
		'current_profile_info': current_profile_info,
	}
	return render(request, 'login.html', context)

def submit_login(request):
	try:
		username = request.POST['username']
		password = request.POST['password']
		user = authenticate(username = username, password = password)

		if user is not None:
			# the pasword verified for the user
			if user.is_active:
				login(request, user)
				profile_info = ProfileInfo.objects.get(user = user)
				return JsonResponse({'success': True, 'location': '/'})
			else:
				return JsonResponse({'success': False})
		else:
			return JsonResponse({'success': False, 'error': 'Incorrect username/password combination'})
	except:
		return JsonResponse({'success': False, 'error': 'Please enter both the username and password'})

def logoff(request):
	logout(request)
	return HttpResponseRedirect('/')

def reagent(request, reagent_id):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	reagent = Reagent.objects.get(id = reagent_id)
	title = 'ProtoCat - ' + str(reagent)
	context = {
		'title': title,
		'current_profile_info': current_profile_info,
		'reagent': reagent
	}
	return render(request, 'reagent.html', context)

def edit_reagent(request, reagent_id):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	reagent = Reagent.objects.get(id = reagent_id)
	title = 'ProtoCat - ' + str(reagent)
	context = {
		'title': title,
		'current_profile_info': current_profile_info,
		'method': 'edit',
		'reagent': reagent
	}
	return render(request, 'edit_reagent.html', context)

def new_reagent(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	title = 'ProtoCat - New Reagent'
	context = {
		'title': title,
		'current_profile_info': current_profile_info,
		'method': 'new'
	}
	return render(request, 'edit_reagent.html', context)

def about(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	context = {
		'title': 'ProtoCat',
		'current_profile_info': current_profile_info,
	}
	return render(request, 'about.html', context)

def search(request):
	search_hidden = False
	text_filter = ""
	try:
		text_filter = request.POST['text_filter']
	except:
		pass

	# get the right way to order them
	# default is by title
	try:
		order = request.POST['sort-order']
		if (order == 'sort-revised-upload-date'):
			order = 'upload_date'
		elif (order == 'sort-title'):
			order = 'title'
		elif (order == 'sort-author'):
			order = 'author__user__username'
		elif (order == 'sort-num-ratings'):
			order = 'num_ratings'
		elif (order == 'sort-avg-rating'):
			order = 'avg_rating'
		elif (order == 'sort-num-steps'):
			order = 'num_steps'
		else:
			order = 'title'
	except:
		order = 'title'

	# get right direction to order results
	sort_direction = ""
	try:
		sort_direction = request.POST['sort-asc-des']
		if (sort_direction == 'asc'):
			sort_direction = ''
		else:
			sort_direction = '-'
	except:
		sort_direction = ""

	order = sort_direction + order

	results = Protocol.objects.filter(Q(title__icontains = text_filter) | Q(description__icontains = text_filter) | Q(materials__icontains = text_filter) | Q(protocol_step__action__icontains = text_filter) | Q(reagentforprotocol__display_name__icontains = text_filter)).distinct()

	try:
		search_hidden = (request.POST['search-hidden'] == "on")
	except:
		pass

	if (not search_hidden):
		results = results.filter(searchable = True)

	# filter the results even more
	try:
		revision_start_date = request.POST['revision-start-upload']
		revision_start_date = revision_start_date.split("/")
		revision_start_date = map(int, revision_start_date)
		my_datetime = datetime.date(revision_start_date[2], revision_start_date[0], revision_start_date[1])
		# try to make timezone aware
		results = results.exclude(upload_date__lt = my_datetime)
	except:
		pass

	try:
		revision_end_date = request.POST['revision-end-upload']
		revision_end_date = revision_end_date.split("/")
		revision_end_date = map(int, revision_end_date)
		my_datetime = datetime.date(revision_end_date[2], revision_end_date[0], revision_end_date[1])
		# try to make timezone aware
		results = results.exclude(upload_date__gt = my_datetime)
	except:
		pass

	try:
		min_num_ratings = int(request.POST['min-num-ratings'])
		results = results.exclude(num_ratings__lt = min_num_ratings)
	except:
		pass

	try:
		max_num_ratings = int(request.POST['max-num-ratings'])
		results = results.exclude(num_ratings__gt = max_num_ratings)
	except:
		pass

	try:
		min_avg_ratings = float(request.POST['min-avg-ratings'])
		results = results.exclude(avg_rating__lt = min_avg_ratings)
	except:
		pass

	try:
		max_avg_ratings = float(request.POST['max-avg-ratings'])
		results = results.exclude(avg_rating__gt = max_avg_ratings)
	except:
		pass

	# get user info
	current_profile_info = request.user

	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None

	# order everything
	results = results.order_by(order)

	context = {
		'title': 'ProtoCat',
		'text_filter': text_filter,
		'results': results,
		'current_profile_info': current_profile_info,
	}
	return render(request, 'search.html', context)

def submit_rating(request):
	try:
		current_profile_info = request.user
		if (not current_profile_info.is_anonymous()):
			current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
			new_value = int(request.POST['NewValue'])
			protocol_id = request.POST['id']
			protocol = Protocol.objects.get(id = protocol_id)
			try:
				old_rating = ProtocolRating.objects.get(person = current_profile_info, protocol = protocol)
				protocol.avg_rating = ((protocol.avg_rating * protocol.num_ratings) - old_rating.score + new_value) / protocol.num_ratings
				old_rating.score = new_value
				old_rating.save()
			except:
				rating = ProtocolRating(person = current_profile_info, score = new_value, protocol = protocol)
				protocol.avg_rating = ((protocol.avg_rating * protocol.num_ratings) + new_value) / (protocol.num_ratings + 1)
				protocol.num_ratings += 1
				rating.save()
			protocol.save()
		context = {
			'title': 'ProtoCat',
			'current_profile_info': current_profile_info,
		}
		return JsonResponse({'success': True})
	except:
		return JsonResponse({'success': False})

def upload_default(request):
	current_data = None
	return upload_page(request, current_data)

def upload_branch(request, protocol_id):
	categories = Category.objects.all()
	protocol = Protocol.objects.get(id = protocol_id)

	protocol_steps = ProtocolStep.objects.filter(protocol = protocol).order_by('step_number')
	protocol_reagents = ReagentForProtocol.objects.filter(protocol = protocol)

	# Reduce copies of the same reagent into a single one
	aggregated_reagents = None
	if (protocol_reagents != None):
		aggregated_reagents = list(protocol_reagents[:1])
		for protocol_reagent in protocol_reagents:
			to_add = True
			for aggregated_reagent in aggregated_reagents:
				if (protocol_reagent.reagent_type == 1 and aggregated_reagent.reagent == protocol_reagent.reagent and aggregated_reagent.unit == protocol_reagent.unit):
					to_add = False
			if (to_add):
				aggregated_reagents.append(protocol_reagent)


	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
		#print(current_profile_info)
	else:
		current_profile_info = None

	try:
		last_reagent_id = protocol_reagents.aggregate(Max('number_in_step')).get('number_in_step__max', 0.00) + 1
	except:
		last_reagent_id = 0

	context = {
		'title': 'ProtoCat - Upload Protocol',
		'current_profile_info': current_profile_info,
		'protocol': protocol,
		'protocol_steps': protocol_steps,
		'categories': categories,
		'protocol_reagents': protocol_reagents,
		# get the highest number to ensure that there are no conflicts
		'last_reagent_id': last_reagent_id
	}
	#print(len(connection.queries))
	if (current_profile_info == None):
		return HttpResponseRedirect('/')
	else:
		return render(request, 'upload_protocol_branch.html', context)

def upload_page(request, current_data):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
		#print(current_profile_info)
	else:
		current_profile_info = None

	categories = Category.objects.all()

	context = {
		'title': 'ProtoCat - Upload Protocol',
		'current_profile_info': current_profile_info,
		'categories': categories,
	}
	#print(len(connection.queries))
	if (current_profile_info == None):
		return HttpResponseRedirect('/')
	else:
		return render(request, 'upload_protocol.html', context)

def submit_upload(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
		#print(current_profile_info)
	else:
		current_profile_info = None

	try:
		# get main data for the Protocol model
		protocol_title = bleach.clean(request.POST['title'])
		protocol_desc = bleach.clean(request.POST['description'])
		protocol_changes = bleach.clean(request.POST['change-log'])

		protocol = Protocol(change_log = protocol_changes, title = protocol_title, description = protocol_desc, author = current_profile_info)

		protocol_cat = ""
		try:
			# get category and associate it with protocol
			protocol_cat = bleach.clean(request.POST['category'])
			cat = Category.objects.get(title = protocol_cat)
			protocol.category = cat
		except:
			pass

		# associate new protocol with previous revision if necessary
		try:
			previous_protocol_id = bleach.clean(request.POST['BranchFrom'])

			if (previous_protocol_id != -1):
				# set up previous revisions and first revision for new protocol
				prev_protocol = Protocol.objects.get(id = previous_protocol_id)
				protocol.previous_revision = prev_protocol
				if (prev_protocol.first_revision != None):
					protocol.first_revision = prev_protocol.first_revision
				else:
					protocol.first_revision = prev_protocol
		except:
			pass
		protocol.save()


		# save the steps now
		num_steps = 0

		# go over each available step
		number_to_check = int(bleach.clean(request.POST['number_to_check']))
		for x in range(0, number_to_check + 1):
			try:
				prefix = 'step' + str(x)
				number = int(bleach.clean(request.POST[prefix + '[number]']))
				description = bleach.clean(request.POST[prefix + '[description]'])

				time = 0
				warning = ""
				title = ""

				# try to pick up each individual part of each step
				try:
					warning = bleach.clean(request.POST[prefix + '[warning]'])
					#print('found warning')
				except:
					warning = ""

				try:
					time = int(bleach.clean(request.POST[prefix + '[time]']))
				except:
					time = -1
				#print(warning)
				ps = ProtocolStep(action = description, warning = warning, step_number = number, time = time, protocol = protocol)
				try:
					title = bleach.clean(request.POST[prefix + '[title]'])
					ps.title = title
				except:
					pass

				ps.save()
				num_steps = num_steps + 1
			except:
				# Means that the name doesn't exist
				# print('error1')
				pass

		protocol.num_steps = num_steps


		# get any written-in reagents and save them
		protocol_rea = ""
		try:
			protocol_rea = bleach.clean(request.POST['text-reagents'])
		except:
			pass

		protocol.materials = protocol_rea

		protocol.save()

	except Exception as e:
		#print('error2')
		#print(e)
		pass

	context = {
		'title': 'ProtoCat - Submit Upload',
		'current_profile_info': current_profile_info,
	}
	return HttpResponseRedirect('/')

def submit_comment(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous() and bleach.clean(request.POST['comment']) != ""):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
		comment = bleach.clean(request.POST['comment'])
		protocol_id = bleach.clean(request.POST['protocol_id'])
		protocol = Protocol.objects.get(id = protocol_id)

		try:
			proto_comment = ProtocolComment(author = current_profile_info, protocol = protocol, note = comment)
			proto_comment.save()
		except:
			pass
	context = {
		'title': 'ProtoCat',
		'current_profile_info': current_profile_info,
		'comment': proto_comment,
	}
	return render(request, 'repeated_parts/comment.html', context)



def update_profile(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
		#print(current_profile_info)
	else:
		current_profile_info = None

	try:
		user_id = request.POST['user_id']
		user = ProfileInfo.objects.get(id = user_id)
		if (current_profile_info == user):
			about = ""
			website = ""
			email = ""
			size = int(request.POST['size'])
			if (size == 1):
				try:
					about = request.POST['about1']
				except:
					pass
				try:
					website = request.POST['website1']
				except:
					pass
				try:
					email = request.POST['email1']
				except:
					pass
			elif (size == 2):
				try:
					about = request.POST['about2']
				except:
					pass
				try:
					website = request.POST['website2']
				except:
					pass
				try:
					email = request.POST['email2']
				except:
					pass

			user.about = about
			user.website = website
			user.user.email = email

			try:
				picture = request.FILES['picture']
				destination = open(settings.MEDIA_ROOT + picture.name , 'wb+')
				for chunk in picture.chunks():
					destination.write(chunk)
				destination.close()
				user.profile_image.save(picture.name, File(open(settings.MEDIA_ROOT + picture.name, "rb")))
			except:
				pass
			user.save()
			user.user.save()
			#print("Done!")
			return JsonResponse({'success': True})
	except Exception as inst:
		#print(inst)
		#print("Update didn't work")
		return JsonResponse({'success': False})

def test(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
		#print(current_profile_info)
	else:
		current_profile_info = None

	context = {
		'title': 'ProtoCat',
		'current_profile_info': current_profile_info,
	}
	return render(request, 'test.html', context)


def toggle_protocol(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
		#print(current_profile_info)
	else:
		current_profile_info = None
	try:
		protocol = Protocol.objects.get(id = request.POST['protocol_id'])
		if (protocol.author == current_profile_info):
			protocol.searchable = not protocol.searchable
			protocol.save()
			return JsonResponse({'success': True})
		else:
			return JsonResponse({'success': False})
	except Exception as inst:
		#print(inst)
		#print("Update didn't work")
		return JsonResponse({'success': False})


def github(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
		#print(current_profile_info)
	else:
		current_profile_info = None
	context = {
		'title': 'ProtoCat',
		'current_profile_info': current_profile_info,
	}
	return render(request, "github.html", context)

def github_post(request):
	gh = GithubId()
	gh.name = request.POST['name']
	gh.save()
	return HttpResponseRedirect('/')

def import_page(request):
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
		#print(current_profile_info)
	else:
		current_profile_info = None

	categories = Category.objects.all()

	context = {
		'title': 'ProtoCat - Upload Protocol',
		'current_profile_info': current_profile_info,
	}
	#print(len(connection.queries))
	if (current_profile_info == None):
		return HttpResponseRedirect('/')
	else:
		return render(request, 'import.html', context)

def submit_import(request):
	conv = converter()
	pio_data = request.FILES['files[]'].file.getvalue()

	pio_json = json.loads(pio_data)
	cat_json = conv.convert_io_to_cat(pio_json)
	
	current_profile_info = request.user
	if (not current_profile_info.is_anonymous()):
		current_profile_info = ProfileInfo.objects.get(user = current_profile_info)
	else:
		current_profile_info = None
	
	try:
		# get main data for the Protocol model
		protocol_title = cat_json['title']
		protocol_desc = cat_json['description']
		protocol_changes = cat_json['change-log']

		protocol = Protocol(change_log = protocol_changes, title = protocol_title, description = protocol_desc, author = current_profile_info)
		
		protocol_cat = ""
		try:
			# get category and associate it with protocol
			protocol_cat = bleach.clean(cat_json['category'])
			cat = Category.objects.get(title = protocol_cat)
			protocol.category = cat
		except:
			pass

		# associate new protocol with previous revision if necessary
		previous_protocol_id = -1

		protocol.save()
		
		for step in cat_json['protocol_steps']:
			ps = ProtocolStep(title=step['title'], action = step['action'], warning = step['warning'],\
				step_number = step['step_number'], time = step['time'], protocol = protocol)
			ps.save()
		protocol.num_steps = len(cat_json['protocol_steps'])
		
		try:
			protocol.materials = bleach.clean(cat_json['materials'])
		except:
			protocol.materials = ""

		protocol.save()

	except Exception as e:
		#print('error2')
		print(e)
		pass

	context = {
		'title': 'ProtoCat - Submit Upload',
		'current_profile_info': current_profile_info,
	}
	return HttpResponseRedirect('/')
		
def toggle_protocol_favorite(request, protocol_id):
	if (request.user.profileinfo.favorites.filter(id = protocol_id)):
		request.user.profileinfo.favorites.remove(protocol_id)
		return JsonResponse({'success': True})
	else:
		request.user.profileinfo.favorites.add(protocol_id)
		return JsonResponse({'success': False})

class NewMessageView (FormView):
	template_name = 'protoChat/new_message.html'
	form_class = forms.NewMessageForm
	
	def get_context_data(self, **kwargs):
		context = super(NewMessageView, self).get_context_data(**kwargs)
		context['title'] = 'New Message'
		if (self.request.user.is_anonymous()):
			context['current_profile_info'] = None
		else:
			context['current_profile_info'] = self.request.user.profileinfo
		return context

	def get_initial(self):
		initial = super(NewMessageView, self).get_initial()
		if 'recip_name' in self.kwargs:
			initial['recipient'] = self.kwargs['recip_name']
		return initial

	def form_valid(self, form):
		if self.request.user.is_anonymous():
			return redirect('root_index')

		sender = ProfileInfo.objects.get(user = self.request.user)
		recip_user = User.objects.get(username = form.cleaned_data.get('recipient'))
		recip = ProfileInfo.objects.get(user = recip_user)
		message = form.cleaned_data.get('message')

		models.Message.objects.create(sender=sender, recipient=recip, message=message)
		return redirect('root_index')

def inbox_view(request):
	if request.method == "POST":
		for key in request.POST:
			if key[:5] == 'check':
				id = key[5:]
				tempMessage = models.Message.objects.get(id=id)
				tempMessage.deleted = True
				tempMessage.save()

	if request.user.is_anonymous():
		return redirect('root_index')
	else:
		user = ProfileInfo.objects.get(user = request.user)
	
	messages = models.Message.objects.filter(recipient=user).filter(deleted=False).order_by('-timeSent')

	for message in messages:
		message.read = True
		message.save()

	context = {
		'title': 'Inbox',
		'message_list': messages,
	}
	if (request.user.is_anonymous()):
		context['current_profile_info'] = None
	else:
		context['current_profile_info'] = request.user.profileinfo
	return render(request, 'protoChat/inbox.html', context)

def get_protocols_from_category(request, category_id):
	if (category_id == ""):
		category_id = None
	else:
		category_id = int(category_id)
	protocols = Protocol.objects.all().filter(category = category_id).filter(searchable = True)
	context = {
		'protocols': protocols
	}
	return render(request, "category_browser_protocols.html", context)

