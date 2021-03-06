from django.http import HttpResponse
from django.shortcuts import render
from speechvisserver.ivfcrvis.recording import *
from sklearn.decomposition import PCA
import json
import random
import csv
import decimal
import scipy.io
from io import BytesIO
import seaborn


def index(request):
    return render(request, 'index.html', {})


def speaker_validation(request):
    coder = request.GET.get('coder', '')
    submit = request.GET.get('submit', '')
    error = ''
    if submit:
        if not coder:
            error = 'Your name is required in the coder field.'
        else:
            annotation_id = request.GET.get('annotation_id')
            annotation = Annotation.objects.get(id=annotation_id)
            segment = annotation.segment
            sensitive = request.GET.get('sensitive', 'false')
            validation = Annotation(segment=segment, sensitive=sensitive,
                coder=coder, method='SPEAKER_VALIDATION')
            validation.speaker = request.GET.get('speaker')
            validation.save()
    records = Annotation.objects.filter(coder='LENA', speaker='CHN').exclude(segment__annotation__coder=coder)
    annotation = records[random.randrange(records.count())]
    context = {
        'coder': coder,
        'recording_id': annotation.segment.recording.id,
        'segment_number': annotation.segment.number,
        'filename': segment.static_path,
        'speaker': annotation.speaker,
        'speaker_descriptive': getDescriptiveName(annotation.speaker),
        'annotation_id': annotation.id,
        'error': error
    }
    return render(request, 'speaker_validation.html', context)


def vocal_categorization(request):
    coder = request.GET.get('coder', '')
    submit = request.GET.get('submit', '')
    error = ''
    if submit:
        if not coder:
            error = 'Your name is required in the coder field.'
        else:
            segment_id = request.GET.get('segment_id')
            segment = Segment.objects.get(id=segment_id)
            annotation = Annotation(segment=segment, coder=coder, method='VOCAL_CATEGORIZATION')
            annotation.category = request.GET.get('category')
            annotation.save()
    records = Segment.objects.filter(annotation__speaker='CHN').exclude(annotation__method='VOCAL_CATEGORIZATION')
    segment = records[random.randrange(records.count())]
    context = {
        'coder': coder,
        'segment': segment,
        'filename': segment.static_path,
        'error': error
    }
    return render(request, 'vocal_categorization.html', context)


def data_manager(request):
    submit = request.GET.get('submit', '')
    error = ''
    if submit == 'save_feature':
        id = request.GET.get('feature_recording_id_option')
        feature = request.GET.get('feature').strip()
        filename = request.GET.get('save_feature_file')
        print('test')
        if not id:
            error = 'Invalid Recording Id'
        elif not feature:
            error = 'Invalid Feature'
        else:
            recording = Recording.objects.get(id=id)
            data = numpy.loadtxt(filename)
            feature = AudioFeature.save_feature(recording, feature, data)
            print(feature)
    if submit == 'import':
        id = request.GET.get('add_recording_id', '').strip()
        directory = request.GET.get('add_recording_directory', '')
        if not id:
            error = 'Invalid Recording Id'
        else:
            recording = Recording(id=id, directory=directory)
            recording.save()
    export_columns = ['number', 'speaker', 'start', 'end']
    acoustic_columns = ['peak_amplitude', 'mean_amplitude', 'pitch']
    export_id = request.GET.get('export', '')
    if Recording.objects.filter(id=export_id).exists():
        selected_columns = []
        for column in export_columns:
            if request.GET.get('export_{}'.format(column), False):
                selected_columns.append(column)
        segments = Segment.objects.filter(recording__id=export_id, annotation__coder='LENA').annotate(speaker=Max('annotation__speaker'))
        export_speakers = request.GET.getlist('export_speakers')
        if len(export_speakers) > 0:
            print('speakers: {}'.format(export_speakers))
            segments = segments.filter(speaker__in=export_speakers)
        data = segments.values_list(*selected_columns)
        export_format = request.GET.get('export_format', 'CSV')
        if export_format == 'CSV':
            return export_csv(data, selected_columns)
        else:
            arrays = values_to_numpy_arrays(data, selected_columns)
            selected_acoustic_columns = []
            for column in acoustic_columns:
                selected_acoustic_columns.append(request.GET.get('export_{}'.format(column), False))
                if selected_acoustic_columns[-1]:
                    arrays[column] = []
            for segment in segments:
                segment.read_audio()
                print('Getting acoustic features for segment {}'.format(segment.number))
                acoustic_features = segment.acoustic_features()
                for column, export in zip(acoustic_columns, selected_acoustic_columns):
                    if export:
                        arrays[column].append(acoustic_features[column])
            if export_format == 'NPZ':
                return export_npz(arrays)
            elif export_format == 'MAT':
                return export_mat(arrays)
            else:
                error = 'Invalid Export Format!'
    context = {
        'export_speakers': ['CHN', 'CXN', 'FAN', 'MAN'],
        'export_formats': ['CSV', 'NPZ', 'MAT'],
        'export_columns': export_columns,
        'acoustic_columns': acoustic_columns,
        'recordings': Recording.objects.all(),
        'error': error
    }
    return render(request, 'data_manager.html', context)


def export_csv(data, columns):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="export.csv"'
    writer = csv.writer(response)
    writer.writerow(columns)
    for row in data:
        writer.writerow(row)
    return response


def values_to_numpy_arrays(data, columns):
    arrays = {}
    for column, index in zip(columns, range(len(columns))):
        dtype = type(data[0][index])
        if dtype == decimal.Decimal:
            dtype = float
        arrays[column] = numpy.array([value[index] for value in data], dtype=dtype)
    return arrays


def export_npz(arrays):
    response = HttpResponse(content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="export.npz"'
    buffer = BytesIO()
    numpy.savez(buffer, **arrays)
    npzFile = buffer.getvalue()
    buffer.close()
    response.write(npzFile)
    return response


def export_mat(arrays):
    response = HttpResponse(content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="export.mat"'
    buffer = BytesIO()
    scipy.io.savemat(buffer, arrays)
    matFile = buffer.getvalue()
    buffer.close()
    response.write(matFile)
    return response
