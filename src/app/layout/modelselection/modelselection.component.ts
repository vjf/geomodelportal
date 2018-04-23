import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, ParamMap } from '@angular/router';
import { routerTransition } from '../../router.animations';
import { HttpErrorResponse } from '@angular/common/http';

import 'rxjs/add/operator/switchMap';

import { ModelInfoService } from '../../shared/services/model-info.service';

@Component({
    selector: 'app-modelselection',
    templateUrl: './modelselection.component.html',
    styleUrls: ['./modelselection.component.scss'],
    animations: [routerTransition()]
})
export class ModelSelectionComponent implements OnInit {

    // Geological models for each provider
    public providerModels: any = {};

    public providerPath = '';

    constructor(private route: ActivatedRoute,
                private modelInfoService: ModelInfoService) {
    }

    ngOnInit() {
        this.providerPath = this.route.snapshot.paramMap.get('providerPath');
        this.modelInfoService.getProviderModelInfo().subscribe(
            data => {
                this.providerModels = data as string [];
                console.log('ProviderModelInfo Loaded', this.providerModels);
                console.log('providerPath=', this.providerPath);
                console.log('this.providerModels[providerPath]=', this.providerModels[this.providerPath]);
            },
            (err: HttpErrorResponse) => {
                console.log('Cannot load JSON', err);
            }
        );
    }

}
